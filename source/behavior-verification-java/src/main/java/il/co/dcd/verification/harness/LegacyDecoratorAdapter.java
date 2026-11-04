package il.co.dcd.verification.harness;

import java.util.Map;
import org.w3c.dom.Element;

/** Execute an original standalone decorator through its verified framework interface. */
public final class LegacyDecoratorAdapter implements BoundaryAdapter {
    private final LegacyBoundaryAdapter framework=new LegacyBoundaryAdapter();
    void configure(Element job){framework.configure(job);}
    public Object invoke(String xml,Map<String,Object> state,Element configuration)throws Exception {
        return framework.invokeDecorator(state,configuration);
    }
    Map<String,Object> snapshot(Map<String,Object> initial)throws Exception{return framework.snapshot(initial);}
}
