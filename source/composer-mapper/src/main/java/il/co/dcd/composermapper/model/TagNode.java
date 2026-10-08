package il.co.dcd.composermapper.model;

import java.util.*;

public class TagNode {
    private final String           tagName;
    private final Map<String,String> attributes = new LinkedHashMap<>();
    private final List<TagNode>    children   = new ArrayList<>();
    /** Decorators that immediately follow this formatter tag in the fmtDef XML */
    private final List<TagNode>    decorators = new ArrayList<>();

    public TagNode(String tagName)              { this.tagName = tagName; }
    public String            getTagName()       { return tagName; }
    public Map<String,String> getAttributes()   { return attributes; }
    public List<TagNode>     getChildren()      { return children; }
    public List<TagNode>     getDecorators()    { return decorators; }
}
