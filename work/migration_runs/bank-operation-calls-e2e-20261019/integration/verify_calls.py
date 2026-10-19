"""Run packaged services with real HTTP calls and an explicitly simulated JDBC boundary."""

import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
JAVA = Path(r'C:\Program Files\Java\jdk-25.0.3\bin\java.exe')
NAMES = ['GetClientLinksOp', 'ValidateClientLinksOp', 'GetClientOverviewOp']


def port():
    """Select an available loopback port for this test process."""
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def request(url, body, headers=None):
    """Capture actual HTTP success or error responses without replacing their contents."""
    try:
        with urlopen(Request(url, data=body.encode(), headers=headers or {'Content-Type':'application/xml'}), timeout=25) as response:
            return response.status, response.read().decode()
    except HTTPError as error:
        return error.code, error.read().decode()


def proxy(target, destination, trace):
    """Log and forward HTTP traffic without simulating a downstream microservice."""
    class Forwarder(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get('Content-Length', '0'))).decode()
            headers = {'Content-Type':self.headers.get('Content-Type',''), 'Accept':self.headers.get('Accept','*/*')}
            event = dict(target=target,path=self.path,request=body,content_type=headers['Content-Type'],started=time.monotonic())
            trace.append(event)
            try:
                status, reply = request(f'http://127.0.0.1:{destination}{self.path}',body,headers)
            except Exception as error:
                status, reply = 502, str(error)
            event.update(status=status,response=reply,finished=time.monotonic())
            self.send_response(status)
            self.send_header('Content-Type','application/xml')
            self.end_headers()
            self.wfile.write(reply.encode())

        def log_message(self, *args):
            return
    server = ThreadingHTTPServer(('127.0.0.1',0),Forwarder)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server


def main():
    """Start all three real packages, record requests and verify the dependency chain."""
    state = ROOT / 'state/migration.db'
    if not state.exists():
        candidates = list((ROOT / 'state').glob('*.db'))
        if len(candidates) != 1:
            raise ValueError('Cannot identify run database')
        state = candidates[0]
    with sqlite3.connect(state) as conn:
        contracts = {key:json.loads(data) for key,data in conn.execute('SELECT operation_key,contract_json FROM operation_service_contracts')}
    ports = {name:port() for name in NAMES}
    trace, processes, logs, servers, scenarios = [], {}, [], {}, []
    report = dict(real_http_services=False,real_requests_completed=0,simulated_boundary='Oracle JDBC procedure and lookup table only',scenarios=scenarios,trace=trace,validation_failures=[])
    report_lock = threading.Lock()
    def check(label, action):
        try:
            return action()
        except Exception as error:
            report['validation_failures'].append(dict(scenario=label,error=str(error)))
            print('FAILED ' + label + ': ' + str(error),flush=True)
            return None
    try:
        for name in NAMES:
            servers[name] = proxy(name,ports[name],trace)
        for name in NAMES:
            project = ROOT / 'services/INTERNET' / name
            jars = [path for path in (project / 'target').glob('*.jar') if not path.name.endswith('-sources.jar')]
            if len(jars) != 1:
                raise ValueError('Expected one executable service package for ' + name)
            log = (ROOT / 'integration' / (name + '.log')).open('w',encoding='utf-8')
            logs.append(log)
            command = [str(JAVA),'-Dserver.address=127.0.0.1',f'-Dserver.port={ports[name]}',f'-Dbank.fixture.log={ROOT / "integration/database-calls.log"}',
                '-Dspring.datasource.url=jdbc:bank-fixture:test','-Dspring.datasource.driver-class-name=validation.FixtureDriver',
                '-Dspring.datasource.username=fixture','-Dspring.datasource.password=fixture']
            for target in NAMES:
                property_name = contracts['INTERNET/' + target]['base_url_property']
                command.append(f'-D{property_name}=http://127.0.0.1:{servers[target].server_port}')
            command.extend(['-cp',os.pathsep.join([str(jars[0]),str(ROOT / 'integration/classes')]),
                            'org.springframework.boot.loader.launch.JarLauncher'])
            processes[name] = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            print('Started ' + name,flush=True)
        for name in NAMES:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                if processes[name].poll() is not None:
                    raise RuntimeError(name + ' exited; inspect its integration log')
                try:
                    with socket.create_connection(('127.0.0.1',ports[name]),timeout=.5):
                        break
                except OSError:
                    time.sleep(.25)
            else:
                raise TimeoutError(name + ' did not start')
        report['real_http_services'] = True
        def invoke(name, client, expected):
            start = len(trace)
            body = f'<GetClientLinks><ClientId>{client}</ClientId><BankId>1</BankId></GetClientLinks>'
            route = contracts['INTERNET/' + name]['path']
            status, reply = request(f'http://127.0.0.1:{ports[name]}{route}',body)
            report['real_requests_completed'] += 1
            events = trace[start:]
            counts = {target:sum(event['target']==target for event in events) for target in NAMES}
            success = 200 <= status < 300 and 'ACCOUNTS' in reply and '/accounts/' + client in reply
            case = dict(operation=name,client=client,status=status,response=reply,downstream_counts=counts,
                        expected_downstream_counts=expected,success_body_verified=success,trace_start=start,trace_end=len(trace))
            scenarios.append(case)
            response_xml = ElementTree.fromstring(reply)
            case['response_root'] = response_xml.tag.rsplit('}',1)[-1]
            if success:
                values = {node.tag.rsplit('}',1)[-1]:node.text for node in response_xml.iter()}
                assert values.get('ClientId') == client, case
                assert values.get('LinkId') == 'ACCOUNTS' and values.get('LinkUrl') == '/accounts/' + client, case
                assert values.get('IsExternal') == 'false' and values.get('IconCode') == 'account', case
                assert values.get('LinkDescription') == 'Account overview', case
            for target, count in expected.items():
                assert counts[target] == count, case
            for event in events:
                assert event['path'] == contracts['INTERNET/' + event['target']]['path'], event
                assert 'application/xml' in event['content_type'], event
                values = {node.tag.rsplit('}',1)[-1]:node.text for node in ElementTree.fromstring(event['request']).iter()}
                assert values.get('ClientId') == client, event
                assert (values.get('BankId') or '').lstrip('0') == '1', event
            return case
        def verify_success(name, expected):
            case = invoke(name,'CLIENT123',expected)
            assert case['success_body_verified'], case
            if name == NAMES[2]:
                events = trace[case['trace_start']:case['trace_end']]
                parent = next(event for event in events if event['target'] == NAMES[1])
                children = [event for event in events if event['target'] == NAMES[0]]
                assert children[0]['started'] < parent['finished'] <= children[1]['started'], events
        for name, expected in [(NAMES[0],{NAMES[0]:0,NAMES[1]:0}),(NAMES[1],{NAMES[0]:1}),(NAMES[2],{NAMES[0]:2,NAMES[1]:1})]:
            check(name + ' success',lambda name=name,expected=expected: verify_success(name,expected))
        def concurrent_request(client):
            body = f'<GetClientLinks><ClientId>{client}</ClientId><BankId>1</BankId></GetClientLinks>'
            status, reply = request(f'http://127.0.0.1:{ports[NAMES[2]]}{contracts["INTERNET/" + NAMES[2]]["path"]}',body)
            with report_lock:
                report['real_requests_completed'] += 1
            result = dict(client=client,status=status,response=reply)
            assert 200 <= status < 300 and '/accounts/' + client in reply, result
            values = {node.tag.rsplit('}',1)[-1]:node.text for node in ElementTree.fromstring(reply).iter()}
            assert values.get('ClientId') == client, result
            return result
        def checked_customer(client):
            return check(client,lambda: concurrent_request(client))
        with ThreadPoolExecutor(max_workers=8) as pool:
            concurrent = list(pool.map(checked_customer,['CONCURRENT' + str(index) for index in range(8)]))
        scenarios.append(dict(scenario='concurrent_customer_requests',results=concurrent,passed=all(result is not None for result in concurrent)))
        def verify_error(client,category,number):
            error = invoke(NAMES[2],client,{})
            assert not error['success_body_verified'], error
            fields = {node.tag.rsplit('}',1)[-1]:node.text for node in ElementTree.fromstring(error['response']).iter()}
            assert int(fields.get('ErrorCategory','-1')) == category and int(fields.get('ErrorNumber','-1')) == number, error
        check('database error',lambda: verify_error('DBERROR',99,8))
        check('no links found',lambda: verify_error('MISSING',20,1))
        processes[NAMES[1]].terminate()
        processes[NAMES[1]].wait(timeout=15)
        def verify_unavailable():
            failure = invoke(NAMES[2],'CLIENT123',{NAMES[0]:0,NAMES[1]:1})
            assert not failure['success_body_verified'], failure
            assert failure['status'] >= 400 or 'Error' in failure['response'], failure
        check('unavailable dependency',verify_unavailable)
        report['passed'] = not report['validation_failures']
        if not report['passed']:
            raise AssertionError(str(len(report['validation_failures'])) + ' integration scenarios failed; inspect report.json')
    except Exception as error:
        report.update(passed=False,error=str(error))
        raise
    finally:
        for process in processes.values():
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
        for server in servers.values():
            server.shutdown()
            server.server_close()
        for log in logs:
            log.close()
        (ROOT / 'integration/report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
