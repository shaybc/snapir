"""Resolve bounded document batches in one shared-policy worker, never one JVM per reference."""

import atexit
from collections import OrderedDict,deque
import logging
import os
from pathlib import Path
from queue import Empty,Queue
import shutil
import struct
import subprocess
from threading import Lock,Thread
from time import monotonic
from xml.etree import ElementTree

from runtime.java_toolchain import java_environment,java_scan_inactivity_timeout
from tools.java_analysis_tools.source_dependencies.analysis_runtime import analyzer_command
from tools.java_analysis_tools.source_dependencies.resolution_index import resolution_index,release_old_indexes

MAX_FRAME=4*1024*1024
_lock=Lock()
_worker=None
_documents=OrderedDict()
_document_bytes=0


class ResolutionWorker:
    """Own one framed worker with bounded diagnostics and inactivity enforcement."""

    def __init__(self):
        base=analyzer_command()
        mapper=Path(__file__).resolve().parents[3]/'composer-mapper/target/composer-mapper-1.1.1-jar-with-dependencies.jar'
        if not mapper.is_file():
            raise ValueError('Shared Java resolution requires the updated Mapper distribution; build with mvn -f source/pom.xml package')
        environment=java_environment()
        executable=shutil.which('java',path=environment.get('PATH') if environment else None)
        self.key=(executable,base[2])
        self.process=subprocess.Popen([executable,'-Xmx256m','-cp',base[2]+os.pathsep+str(mapper),
            'il.co.dcd.javaanalysis.ReferenceResolutionMain'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment)
        self.last_activity=monotonic();self.diagnostics=deque(maxlen=16)
        self.reader=Thread(target=self._diagnostics,daemon=True,name='java-resolution-diagnostics');self.reader.start()

    def _diagnostics(self):
        while chunk:=os.read(self.process.stderr.fileno(),4096):
            self.last_activity=monotonic()
            text=chunk.decode('utf-8',errors='replace');self.diagnostics.append(text)
            logging.getLogger(__name__).debug('Shared Java resolver: %s',text.rstrip())

    def _read(self,count):
        output=bytearray()
        while len(output)<count:
            chunk=os.read(self.process.stdout.fileno(),min(65536,count-len(output)))
            if not chunk:
                raise ValueError('Shared Java resolver exited: '+''.join(self.diagnostics)[-3000:])
            self.last_activity=monotonic();output.extend(chunk)
        return bytes(output)

    def resolve(self,database,payload):
        result=Queue(maxsize=1)
        def transfer():
            try:
                for frame in (str(database).encode('utf-8'),payload):
                    self.process.stdin.write(struct.pack('>I',len(frame)));self.process.stdin.write(frame)
                    self.process.stdin.flush();self.last_activity=monotonic()
                size=struct.unpack('>I',self._read(4))[0]
                if size>MAX_FRAME:
                    raise ValueError('Shared Java resolver response exceeds 4 MiB')
                result.put((self._read(size),None))
            except BaseException as error:
                result.put((None,error))
        thread=Thread(target=transfer,daemon=True,name='java-resolution-batch');thread.start()
        self.last_activity=monotonic()
        try:
            while True:
                try:
                    output,error=result.get(timeout=0.2)
                    if error:
                        raise error
                    return output
                except Empty:
                    if monotonic()-self.last_activity>=java_scan_inactivity_timeout():
                        raise ValueError('Shared Java reference resolver stopped responding without output activity')
        except BaseException:
            self.close()
            raise
        finally:
            thread.join(timeout=5)

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        self.reader.join(timeout=5)
        for pipe in (self.process.stdin,self.process.stdout,self.process.stderr):
            pipe.close()


def _close_worker():
    global _worker
    if _worker is not None:
        _worker.close();_worker=None


def resolve_reference_batch(reference,document,index,path,owner,override):
    """Batch all sites/import requirements in a captured unit using the canonical Java policy."""
    global _worker,_document_bytes
    with _lock:
        database=resolution_index(index)
        key=(str(database),id(document),str(path),owner,override,len(document),document.get('package'))
        site=(reference.get('name'),reference.get('kind'),reference.get('offset','-1'))
        cached=_documents.get(key)
        if cached and cached[0] is document and site in cached[1]:
            _documents.move_to_end(key)
            return cached[1][site]
        source=ElementTree.Element('source',path=str(Path(path).resolve()),package=document.get('package',''))
        if override:
            source.set('override_owner','true')
            if owner is not None:
                source.set('owner_project',owner)
        size=0
        for child in document:
            size+=sum(len(name)+len(value) for name,value in child.attrib.items())*4+64
            if size>MAX_FRAME:
                raise ValueError('Source syntax exceeds the 4 MiB resolution transfer budget; use an indexed map')
            source.append(ElementTree.Element(child.tag,dict(child.attrib)))
            if child.tag=='import' and not child.get('name','').endswith('.*'):
                name=child.get('name')
                if child.get('static')=='true':name=name.rsplit('.',1)[0]
                ElementTree.SubElement(source,'reference',name=name,kind='type',offset='-1')
        ElementTree.SubElement(source,'reference',name=site[0],kind=site[1],offset=site[2])
        payload=ElementTree.tostring(source,encoding='utf-8')
        if len(payload)>MAX_FRAME:
            raise ValueError('Source syntax exceeds the 4 MiB resolution transfer budget')
        environment=java_environment();base=analyzer_command()
        executable=shutil.which('java',path=environment.get('PATH') if environment else None)
        if _worker is None or _worker.process.poll() is not None or _worker.key!=(executable,base[2]):
            _close_worker();_worker=ResolutionWorker();atexit.register(_close_worker)
        result=ElementTree.fromstring(_worker.resolve(database,payload))
        values={(node.get('name'),node.get('kind'),node.get('offset')):
            ([target.get('path') for target in node.findall('target')],node.get('issue')) for node in result}
        weight=len(payload)*4+len(values)*256
        if cached:
            _document_bytes-=cached[2];del _documents[key]
        while _documents and (_document_bytes+weight>32*1024*1024 or len(_documents)>=16):
            _,old=_documents.popitem(last=False);_document_bytes-=old[2]
        if weight<=32*1024*1024:
            _documents[key]=(document,values,weight);_document_bytes+=weight
        release_old_indexes(database)
        return values[site]
