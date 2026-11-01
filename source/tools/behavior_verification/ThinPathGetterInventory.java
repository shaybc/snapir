import java.lang.reflect.*;
import java.util.*;
import javax.xml.stream.*;

/** Inspect compiled native getters without initializing or invoking candidate classes. Experiment only. */
public final class ThinPathGetterInventory {
    private static Class<?> type(String name) throws Exception {
        return switch(name) {
            case "int" -> int.class; case "long" -> long.class; case "boolean" -> boolean.class;
            case "double" -> double.class; case "float" -> float.class; case "short" -> short.class;
            case "byte" -> byte.class; case "char" -> char.class;
            default -> Class.forName(name, false, ClassLoader.getSystemClassLoader());
        };
    }
    public static void main(String[] args) throws Exception {
        Class<?> owner = type(args[0]);
        Class<?>[] parameters = new Class<?>[args.length-2];
        for (int i=2;i<args.length;i++) parameters[i-2]=type(args[i]);
        Method entry = owner.getMethod(args[1], parameters);
        XMLStreamWriter out=XMLOutputFactory.newFactory().createXMLStreamWriter(System.out,"UTF-8");
        out.writeStartElement("inventory"); out.writeAttribute("result_type",entry.getReturnType().getName());
        Set<Class<?>> visited=new HashSet<>();
        List<Class<?>> pending=new ArrayList<>();pending.add(entry.getReturnType());
        for(Class<?> parameter:parameters) pending.add(parameter);
        for(int i=0;i<pending.size() && i<128;i++) {
            Class<?> current=pending.get(i);
            if(!current.getName().startsWith("com.company.generated.") || !visited.add(current))continue;
            out.writeStartElement("type");out.writeAttribute("name",current.getName());
            Method[] methods=current.getMethods();Arrays.sort(methods,Comparator.comparing(Method::toGenericString));
            for(Method method:methods) {
                if(method.getParameterCount()!=0 || Modifier.isStatic(method.getModifiers()) || method.isBridge() || method.isSynthetic()
                    || method.getReturnType()==void.class || !method.getDeclaringClass().getName().startsWith("com.company.generated."))continue;
                out.writeEmptyElement("getter");out.writeAttribute("name",method.getName());
                out.writeAttribute("type",method.getReturnType().getName());pending.add(method.getReturnType());
            }
            out.writeEndElement();
        }
        if(pending.size()>128 && visited.size()>=128)throw new IllegalStateException("Getter inventory limit exceeded");
        out.writeEndElement();out.flush();
    }
}
