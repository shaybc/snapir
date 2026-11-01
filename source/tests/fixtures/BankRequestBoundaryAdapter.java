package fixture;

import il.co.dcd.verification.harness.BoundaryAdapter;
import java.io.StringReader;
import java.text.SimpleDateFormat;
import java.util.Map;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.xml.sax.InputSource;

/** Independent native test fixture, not AI-generated or a live-conversion acceptance artifact. */
public class BankRequestBoundaryAdapter implements BoundaryAdapter {
    public Object invoke(String xml, Map<String, Object> context, Element configuration) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
        Element root = factory.newDocumentBuilder().parse(new InputSource(new StringReader(xml))).getDocumentElement();
        String client = text(root, "ClientId");
        require(client); context.put("ClientId", client);
        String account = text(root, "AccountNumber");
        if (account != null) account = account.replaceFirst("^[" + java.util.regex.Pattern.quote("0") + "]+", "");
        require(account); context.put("AccountNumber", account);
        String session = text(root, "SessionToken");
        require(session); context.put("SessionToken", session);
        String from = text(root, "FromDate");
        if (from != null && !from.isBlank()) context.put("FromDate", new SimpleDateFormat("yyyyMMdd").parse(from));
        String to = text(root, "ToDate");
        if (to != null && !to.isBlank()) context.put("ToDate", new SimpleDateFormat("yyyyMMdd").parse(to));
        String maximum = text(root, "MaxTransactions");
        if (maximum != null && !maximum.isBlank()) {
            maximum = maximum.replaceFirst("^0+(?!$)", "");
            if (maximum.isEmpty()) maximum = "0";
        }
        if (maximum == null || maximum.isEmpty()) maximum = "0";
        context.put("MaxTransactions", maximum);
        return null;
    }
    private static void require(String value) {
        if (value == null || value.isEmpty()) throw new IllegalArgumentException("Mandatory value is missing");
    }
    private static String text(Element root, String name) {
        for (Node child = root.getFirstChild(); child != null; child = child.getNextSibling())
            if (child instanceof Element element && element.getTagName().equals(name)) return element.getTextContent();
        return null;
    }
}
