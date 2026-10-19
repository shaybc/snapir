package com.company.generated.operations.routing;

import com.company.generated.operations.GetClientLinksOpService;
import com.company.generated.units.u3a42c4326e3d.DatabaseErrorStep;
import com.company.generated.units.u3a42c4326e3d.OperationContext;
import com.company.generated.units.u3643d2141e0a.NoLinksFoundStep;
import com.company.generated.units.u42b95631a186.GetClientLinksStep;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestXml;
import com.company.generated.units.u9d214a54d7b1.TechnicalErrorStep;

import org.junit.jupiter.api.Test;

import javax.sql.DataSource;
import java.sql.Connection;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

public class Routef51512412cadTest {

    @Test
    void testGetClientLinksSuccessRoute() throws Exception {
        GetClientLinksStep getClientLinksStep = mock(GetClientLinksStep.class);
        NoLinksFoundStep noLinksFoundStep = mock(NoLinksFoundStep.class);
        DatabaseErrorStep databaseErrorStep = mock(DatabaseErrorStep.class);
        TechnicalErrorStep technicalErrorStep = mock(TechnicalErrorStep.class);
        DataSource dataSource = mock(DataSource.class);
        Connection connection = mock(Connection.class);

        when(dataSource.getConnection()).thenReturn(connection);

        when(getClientLinksStep.execute(any(OperationContext.class))).thenAnswer(invocation -> {
            OperationContext ctx = invocation.getArgument(0);
            ctx.setValueAt("ClientId", "C123");
            List<Object> links = new ArrayList<>();
            Map<String, Object> link = new HashMap<>();
            link.put("LinkId", "L1");
            link.put("LinkDescription", "Home Page");
            link.put("LinkUrl", "https://bank.com");
            link.put("IsExternal", Boolean.FALSE);
            link.put("IconCode", "HOME");
            links.add(link);
            ctx.setValueAt("Links", links);
            return 0;
        });

        GetClientLinksOpService service = new GetClientLinksOpService(
                getClientLinksStep,
                noLinksFoundStep,
                databaseErrorStep,
                technicalErrorStep,
                dataSource
        );

        GetClientLinksRequestXml requestXml = new GetClientLinksRequestXml();
        requestXml.clientId = "C123";
        requestXml.bankId = "B1";

        String result = service.execute(requestXml);

        assertNotNull(result);
        assertTrue(result.contains("C123"));
        assertTrue(result.contains("L1"));
        assertTrue(result.contains("Home Page"));

        verify(getClientLinksStep).execute(any(OperationContext.class));
        verify(dataSource).getConnection();
        verify(connection).close();
    }
}
