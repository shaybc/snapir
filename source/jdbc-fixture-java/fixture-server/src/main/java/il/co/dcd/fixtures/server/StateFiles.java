package il.co.dcd.fixtures.server;

import il.co.dcd.fixtures.protocol.Json;
import java.io.IOException;
import java.nio.channels.*;
import java.nio.file.*;
import java.util.*;

/** Atomic runtime state and bounded ownership locks, separate from immutable tool/fixture stores. */
final class StateFiles {
    private StateFiles() { }
    static Map<String,Object> read(Path directory) throws IOException {
        Path path=directory.resolve("server.json");return Files.exists(path) ? Json.object(Json.read(Files.readAllBytes(path))) : Map.of();
    }
    static void write(Path directory,Map<String,Object> value) throws IOException {
        Files.createDirectories(directory);Path temporary=Files.createTempFile(directory,".state-",".json");
        try {
            Files.write(temporary,Json.bytes(value));
            try { Files.move(temporary,directory.resolve("server.json"),StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING); }
            catch (AtomicMoveNotSupportedException e) { Files.move(temporary,directory.resolve("server.json"),StandardCopyOption.REPLACE_EXISTING); }
        } finally { Files.deleteIfExists(temporary); }
    }
    static OwnedLock lock(Path directory,String name,long timeout) throws Exception {
        Files.createDirectories(directory);FileChannel channel=FileChannel.open(directory.resolve(name),StandardOpenOption.CREATE,StandardOpenOption.WRITE);
        long end=System.nanoTime()+java.util.concurrent.TimeUnit.MILLISECONDS.toNanos(timeout);
        try {
            do {
                try { FileLock lock=channel.tryLock();if(lock!=null) return new OwnedLock(channel,lock); }
                catch (OverlappingFileLockException ignored) { }
                Thread.sleep(25);
            } while(System.nanoTime()<end);
            throw new IllegalStateException("Fixture lifecycle lock timed out");
        } catch(Exception e) { channel.close();throw e; }
    }
    record OwnedLock(FileChannel channel,FileLock lock) implements AutoCloseable {
        @Override public void close() throws IOException { lock.release();channel.close(); }
    }
    static Map<String,Object> publicState(Map<String,Object> state) {
        Map<String,Object> result=new LinkedHashMap<>(state);result.remove("owner_token");return result;
    }
}
