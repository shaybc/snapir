package il.co.dcd.fixtures.protocol;

import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

/** Strict parsing of the fixture JDBC subprotocol; no database vendor is intercepted. */
public record FixtureUrl(URI endpoint, String scenario, String resource, String execution) {
    public static final String PREFIX = "jdbc:fixtures:";
    public static FixtureUrl parse(String text) {
        if (text == null || !text.startsWith(PREFIX)) throw new IllegalArgumentException("Not a fixture JDBC URL");
        URI uri;
        try{uri=URI.create("http:" + text.substring(PREFIX.length()));}
        catch(IllegalArgumentException e){throw new IllegalArgumentException("Malformed fixture JDBC URL");}
        if (uri.getHost()==null || uri.getPort()<1 || uri.getPort()>65535 || uri.getRawUserInfo()!=null || uri.getFragment()!=null)
            throw new IllegalArgumentException("Fixture URL requires host, explicit port and no credentials");
        String path=uri.getRawPath();
        if (path==null || !path.matches("/[^/]+")) throw new IllegalArgumentException("Fixture URL requires one scenario");
        String scenario=decode(path.substring(1));
        if (!scenario.matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}")) throw new IllegalArgumentException("Invalid scenario ID");
        Map<String,String> options=new HashMap<>();
        if (uri.getRawQuery()!=null) for (String pair : uri.getRawQuery().split("&",-1)) {
            String[] item=pair.split("=",2);
            if (item.length!=2 || options.put(decode(item[0]),decode(item[1]))!=null)
                throw new IllegalArgumentException("Invalid or repeated URL option");
        }
        if (!Set.of("resource","execution").containsAll(options.keySet())) throw new IllegalArgumentException("Unknown URL option");
        for (String value : options.values()) if (!value.matches("[A-Za-z0-9][A-Za-z0-9_.-]{0,127}"))
            throw new IllegalArgumentException("Invalid URL option value");
        try { return new FixtureUrl(new URI("http",null,uri.getHost(),uri.getPort(),null,null,null),scenario,
            options.get("resource"),options.getOrDefault("execution",UUID.randomUUID().toString())); }
        catch (URISyntaxException e) { throw new IllegalArgumentException("Invalid server address",e); }
    }
    private static String decode(String value) {
        try{return URLDecoder.decode(value.replace("+","%2B"),StandardCharsets.UTF_8);}
        catch(IllegalArgumentException e){throw new IllegalArgumentException("Malformed fixture URL encoding");}
    }
    public boolean local() {
        try { return InetAddress.getByName(endpoint.getHost()).isLoopbackAddress(); }
        catch (UnknownHostException e) { return false; }
    }
}
