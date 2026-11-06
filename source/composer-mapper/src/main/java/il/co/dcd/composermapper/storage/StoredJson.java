package il.co.dcd.composermapper.storage;

import com.fasterxml.jackson.core.*;
import java.util.*;
import java.io.IOException;
import il.co.dcd.composermapper.util.JsonOutput;

/** Decode one bounded record; whole-project JSON is never a storage or reader contract. */
public final class StoredJson {
    private static final JsonFactory FACTORY=JsonFactory.builder().streamReadConstraints(StreamReadConstraints.builder()
        .maxStringLength(4*1024*1024).maxNestingDepth(128).build()).build();
    private StoredJson(){}
    public static String encode(Object value){String text=JsonOutput.encode(value);if(text.getBytes(java.nio.charset.StandardCharsets.UTF_8).length>4*1024*1024)throw new IllegalArgumentException("Analysis record exceeds 4 MiB; normalize child rows");return text;}
    public static Map<String,Object> map(String text){
        if(text.length()>4*1024*1024)throw new IllegalArgumentException("Oversized analysis record");
        try(var parser=FACTORY.createParser(text)) {parser.nextToken();return (Map<String,Object>)read(parser);}
        catch(IOException error){throw new IllegalArgumentException("Invalid persisted analysis record",error);}
    }
    private static Object read(JsonParser parser)throws IOException {
        return switch(parser.currentToken()) {
            case START_OBJECT -> {Map<String,Object> value=new LinkedHashMap<>();while(parser.nextToken()!=JsonToken.END_OBJECT){String key=parser.currentName();parser.nextToken();value.put(key,read(parser));}yield value;}
            case START_ARRAY -> {List<Object> value=new ArrayList<>();while(parser.nextToken()!=JsonToken.END_ARRAY)value.add(read(parser));yield value;}
            case VALUE_STRING -> parser.getText();case VALUE_TRUE -> true;case VALUE_FALSE -> false;case VALUE_NULL -> null;
            case VALUE_NUMBER_INT -> parser.getBigIntegerValue();case VALUE_NUMBER_FLOAT -> parser.getDecimalValue();
            default -> throw new IOException("Unsupported record token: "+parser.currentToken());
        };
    }
}
