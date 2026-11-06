package il.co.dcd.composermapper.storage;

import java.io.*;
import java.nio.file.*;
import java.security.*;
import java.sql.*;
import java.util.HexFormat;

/** Copy verified identical final notes into a fresh revision without linking mutable files. */
final class NoteReuse implements AutoCloseable {
    private final Path root;
    private final Connection connection;
    private final PreparedStatement lookup;
    private int reused;

    NoteReuse(Path root) throws Exception {
        this.root=root.toRealPath();
        connection=DriverManager.getConnection("jdbc:sqlite:"+this.root.resolve("analysis/analysis.sqlite").toUri()+"?mode=ro&immutable=1");
        try(var statement=connection.createStatement()){statement.execute("PRAGMA cache_size=-8192");}
        lookup=connection.prepareStatement("SELECT note_hash FROM notes WHERE path=?");
    }

    /** The expected digest comes from this generation's finalized metadata and content. */
    boolean copy(String relative,Path target,String expected) throws IOException {
        try {
            lookup.setString(1,relative);
            try(var row=lookup.executeQuery()){if(!row.next()||!expected.equals(row.getString(1)))return false;}
            Path previous=root.resolve(relative).normalize();
            if(!previous.startsWith(root)||!previous.toRealPath().startsWith(root))throw new IOException("Unsafe previous note: "+relative);
            MessageDigest hash=MessageDigest.getInstance("SHA-256");
            try(var input=new DigestInputStream(Files.newInputStream(previous),hash);var output=Files.newOutputStream(target)) {
                byte[] buffer=new byte[65536];long total=0;int count;
                while((count=input.read(buffer))!=-1) {
                    if((total+=count)>4L*1024*1024)throw new IOException("Previous note exceeds the 4 MiB reuse budget: "+relative);
                    output.write(buffer,0,count);
                }
            }
            if(!expected.equals(HexFormat.of().formatHex(hash.digest())))throw new IOException("Previous note changed during reuse: "+relative);
            reused++;return true;
        }catch(SQLException|NoSuchAlgorithmException error){throw new IOException("Could not reuse previous note: "+relative,error);}
    }

    int count(){return reused;}
    public void close(){try{lookup.close();connection.close();}catch(SQLException error){throw new IllegalStateException(error);}}
}
