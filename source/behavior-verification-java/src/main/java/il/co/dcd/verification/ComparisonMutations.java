package il.co.dcd.verification;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParserConfiguration;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.*;
import com.github.javaparser.ast.stmt.*;
import java.nio.file.Path;
import java.util.Set;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.*;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import org.w3c.dom.*;

/** Produce bounded single-site mutations in disposable source, with exact executed-site probes. */
public final class ComparisonMutations {
    private static final String RUNTIME="il.co.dcd.verification.harness.BoundaryRuntime";
    private ComparisonMutations() { }

    public static void main(String[] args) throws Exception {
        var factory=DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl",true);
        var input=factory.newDocumentBuilder().parse(Path.of(args[0]).toFile());
        var output=factory.newDocumentBuilder().newDocument();
        var root=output.createElement("mutations");output.appendChild(root);
        int limit=Integer.parseInt(input.getDocumentElement().getAttribute("limit"));
        var parser=new JavaParser(new ParserConfiguration().setLanguageLevel(ParserConfiguration.LanguageLevel.BLEEDING_EDGE));
        var files=input.getElementsByTagName("file");
        for(int index=0;index<files.getLength() && root.getChildNodes().getLength()<limit;index++) {
            var file=(Element)files.item(index);
            var parsed=parser.parse(file.getTextContent());
            if(!parsed.isSuccessful())throw new IllegalArgumentException("Mutation source cannot be parsed: "+file.getAttribute("path"));
            var unit=parsed.getResult().orElseThrow();
            for(Node node:unit.findAll(Node.class)) {
                if(root.getChildNodes().getLength()>=limit)break;
                if(node.findAncestor(MethodDeclaration.class).isEmpty())continue;
                String kind=null;Node replacement=null;
                String id="comparison-mutant-"+root.getChildNodes().getLength();
                if(node instanceof IfStmt branch) {
                    kind="negated_condition";
                    replacement=branch.clone();
                    ((IfStmt)replacement).setCondition(parser.parseExpression(RUNTIME+".condition(\""+id+"\", !("+branch.getCondition()+"))").getResult().orElseThrow());
                } else if(node instanceof ReturnStmt statement && statement.getExpression().isPresent()) {
                    var value=statement.getExpression().orElseThrow();
                    String changed=value instanceof BooleanLiteralExpr b?String.valueOf(!b.getValue()):
                        value instanceof IntegerLiteralExpr?"0".equals(value.toString())?"1":"0":null;
                    if(changed!=null) {
                        kind="changed_return";
                        replacement=parser.parseStatement("return "+RUNTIME+".value(\""+id+"\", "+changed+");").getResult().orElseThrow();
                    }
                } else if(node instanceof StringLiteralExpr literal) {
                    kind="changed_literal";
                    String value=literal.asString();
                    String changed=value.contains("xsi:")?value.replace("xsi:","wtc:"):value+"__mutation";
                    replacement=parser.parseExpression(RUNTIME+".value(\""+id+"\", "+new StringLiteralExpr().setString(changed)+")").getResult().orElseThrow();
                } else if(node instanceof ExpressionStmt statement && statement.getExpression() instanceof MethodCallExpr call
                    && (Set.of("put","setValueAt").contains(call.getNameAsString()) || call.getNameAsString().startsWith("set"))) {
                    kind="removed_write";
                    replacement=parser.parseStatement("{ "+RUNTIME+".hit(\""+id+"\", \"removed\"); }").getResult().orElseThrow();
                }
                if(kind==null)continue;
                var clone=unit.clone();
                var target=clone.findAll(Node.class).stream().filter(candidate->candidate.getClass()==node.getClass()
                    && candidate.getRange().equals(node.getRange())).findFirst().orElseThrow();
                if(!target.replace(replacement))throw new IllegalArgumentException("Cannot replace mutation site");
                var mutant=output.createElement("mutation");root.appendChild(mutant);
                mutant.setAttribute("id",id);mutant.setAttribute("kind",kind);mutant.setAttribute("path",file.getAttribute("path"));
                mutant.setAttribute("line",String.valueOf(node.getBegin().orElseThrow().line));
                mutant.setTextContent(clone.toString());
            }
        }
        TransformerFactory.newInstance().newTransformer().transform(new DOMSource(output),new StreamResult(Path.of(args[1]).toFile()));
    }
}
