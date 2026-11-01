package com.ibm.il.dse.cc.format;

import com.ibm.dse.base.AttributeXmlFormatDecoratorImpl;
import com.ibm.dse.base.Context;
import com.ibm.dse.base.FormatDecoratorHolder;
import com.ibm.dse.base.Tag;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Small demo format tree with explicit child and decorator registration. */
public abstract class AbstractFormatElement {
    private final List<AbstractFormatElement> children = new ArrayList<>();
    private final List<FormatDecoratorHolder> decorators = new ArrayList<>();
    private final List<AttributeXmlFormatDecoratorImpl> attributes = new ArrayList<>();

    public void initializeFrom(Tag tag) { }
    public abstract String format(Context context) throws Exception;
    public abstract void unformat(String xml, Context context) throws Exception;

    public void addChild(AbstractFormatElement child) { children.add(child); }
    public void addDecorator(FormatDecoratorHolder decorator) { decorators.add(decorator); }
    public void addAttributeDecorator(AttributeXmlFormatDecoratorImpl decorator) { attributes.add(decorator); }
    protected List<AbstractFormatElement> childFormats() { return children; }

    protected String applyDecorators(String value) {
        for (FormatDecoratorHolder decorator : decorators) value = decorator.addDecoration(value);
        return value;
    }

    protected String removeDecorators(String value) {
        for (int i = decorators.size() - 1; i >= 0; i--) value = decorators.get(i).removeDecoration(value);
        return value;
    }

    protected String formatChildren(Context context) throws Exception {
        StringBuilder result = new StringBuilder();
        for (AbstractFormatElement child : children) result.append(child.format(context));
        return result.toString();
    }

    protected void unformatChildren(String xml, Context context) throws Exception {
        for (AbstractFormatElement child : children) child.unformat(xml, context);
    }

    protected String extractElement(String xml, String name) { return DemoXml.value(xml, name); }

    /** Attribute decorators run against the final field value and actual runtime context. */
    protected String element(String name, String value, Context context) {
        return render(name, value, context, false);
    }

    protected String container(String name, String xml, Context context) {
        return render(name, applyDecorators(xml), context, true);
    }

    private String render(String name, String value, Context context, boolean rawXml) {
        StringBuilder result = new StringBuilder("<").append(name);
        for (AttributeXmlFormatDecoratorImpl decorator : attributes) {
            for (Map.Entry<String, String> entry : decorator.formatXmlAttributes(context, value).entrySet()) {
                if (entry.getKey().startsWith("xsi:")) result.append(" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"");
                result.append(" ").append(entry.getKey()).append("=\"").append(DemoXml.escape(entry.getValue())).append("\"");
            }
        }
        if (value == null) return result.append("/>").toString();
        return result.append(">").append(rawXml ? value : DemoXml.escape(value)).append("</").append(name).append(">").toString();
    }
}
