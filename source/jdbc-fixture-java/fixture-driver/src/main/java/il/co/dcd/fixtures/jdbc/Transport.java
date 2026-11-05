package il.co.dcd.fixtures.jdbc;

import il.co.dcd.fixtures.protocol.*;
import java.io.*;
import java.net.*;
import java.net.http.*;
import java.sql.*;
import java.time.Duration;
import java.util.*;

/** Bounded HTTP transport; executions are never retried automatically. */
final class Transport implements AutoCloseable {
    private final HttpClient client;
    private final URI endpoint;
    private final int defaultTimeout;
    int networkTimeout;
    Transport(URI endpoint,Properties properties) {
        this.endpoint=endpoint;
        int login=DriverManager.getLoginTimeout();
        int connect=Integer.parseInt(properties.getProperty("connectTimeoutMs",login>0 ? Integer.toString(Math.multiplyExact(login,1000)) : "5000"));
        defaultTimeout=Integer.parseInt(properties.getProperty("readTimeoutMs","10000"));
        if (connect<1 || defaultTimeout<1) throw new IllegalArgumentException("Timeouts must be positive");
        client=HttpClient.newBuilder().connectTimeout(Duration.ofMillis(connect)).build();
    }
    Map<String,Object> call(String method,String path,Object payload) throws SQLException {
        try {
            byte[] body=payload==null ? new byte[0] : Json.bytes(Values.encode(payload));
            if (body.length>Json.MAX_BYTES) throw new SQLException("JDBC request byte limit exceeded","FXSIZE");
            HttpRequest request=HttpRequest.newBuilder(endpoint.resolve(path))
                .timeout(Duration.ofMillis(networkTimeout>0 ? networkTimeout : defaultTimeout))
                .header("Content-Type","application/json").method(method,
                    body.length==0 ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofByteArray(body)).build();
            HttpResponse<InputStream> response=client.send(request,HttpResponse.BodyHandlers.ofInputStream());
            byte[] bytes;
            try (InputStream input=response.body()) { bytes=input.readNBytes(Json.MAX_BYTES+1); }
            Map<String,Object> value=Json.object(Values.decode(Json.read(bytes)));
            String outcome=(String)value.get("outcome");
            if ("sql_exception".equals(outcome)) throw new SQLException((String)value.getOrDefault("message","Prepared database exception"),"FXPRE");
            if (!"ok".equals(outcome)) {
                String code=(String)value.getOrDefault("code","PROTOCOL_ERROR");
                if ("CAPABILITY_UNSUPPORTED".equals(code)) throw new SQLFeatureNotSupportedException("Fixture JDBC capability unsupported","FXCAP");
                throw new SQLException("Fixture infrastructure failure: "+code,"FIXTURE_MISS".equals(code) ? "FXMIS" : "FXERR");
            }
            if (response.statusCode()!=200) throw new SQLException("Invalid fixture HTTP status","08006");
            return value;
        } catch (HttpTimeoutException e) { throw new SQLTimeoutException("Fixture server timed out","08006",e); }
        catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new SQLException("Fixture request interrupted","08006",e); }
        catch (IOException | IllegalArgumentException e) { throw new SQLException("Fixture transport or response failed","08006",e); }
    }
    @Override public void close() { client.close(); }
}
