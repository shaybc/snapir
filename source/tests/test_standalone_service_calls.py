"""Exercise a standalone operation calling another operation through an injected HTTP URL."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import subprocess
from threading import Thread

import pytest

from test_standalone_runner import launcher_classes


@pytest.mark.parametrize('configured', [True, False])
def test_standalone_resolves_registered_service_constructor_property(launcher_classes, configured):
    directory, classpath = launcher_classes
    source = directory / 'HttpOperation.java'
    source.write_text('''public class HttpOperation {
 private final String host;
 @java.beans.ConstructorProperties({"custom.service.url"})
 public HttpOperation(String host){this.host=host;}
 public String execute(String xml) throws Exception {
  var request=java.net.http.HttpRequest.newBuilder(java.net.URI.create(host+"/operations/WEB/A"))
   .POST(java.net.http.HttpRequest.BodyPublishers.ofString(xml)).build();
  return java.net.http.HttpClient.newHttpClient().send(request,java.net.http.HttpResponse.BodyHandlers.ofString()).body();
 }
}''')
    result = subprocess.run(['javac', '-cp', classpath, str(source)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path, self.rfile.read(int(self.headers['Content-Length'])).decode()))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'<Reply>shared</Reply>')

        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        runtime = directory / 'http-runtime.json'
        runtime.write_text(json.dumps(dict(databases={'default': {}}, service_urls={
            'custom.service.url': 'http://127.0.0.1:' + str(server.server_port)} if configured else {})))
        binding = directory / 'http-operation.json'
        binding.write_text(json.dumps(dict(service_class='HttpOperation', runtime_config=runtime.name)))
        result = subprocess.run(['java', '-cp', classpath, 'StandaloneOperationRunner', str(binding), '-'],
                                input='<Request/>', capture_output=True, text=True, timeout=60)
        if configured:
            assert result.returncode == 0, result.stderr
            assert result.stdout == '<Reply>shared</Reply>'
            assert requests == [('/operations/WEB/A', '<Request/>')]
        else:
            assert result.returncode != 0 and not requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
