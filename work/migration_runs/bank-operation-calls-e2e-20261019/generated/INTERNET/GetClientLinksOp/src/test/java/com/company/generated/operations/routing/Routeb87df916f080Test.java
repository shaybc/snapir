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

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

public class Routeb87df916f080Test {

    @Test
    public void testGetClientLinksNoLinksFoundRouting() throws Exception {
        GetClientLinksStep getClientLinksStep = mock(GetClientLinksStep.class);
        NoLinksFoundStep noLinksFoundStep = mock(NoLinksFoundStep.class);
        DatabaseErrorStep databaseErrorStep = mock(DatabaseErrorStep.class);
        TechnicalErrorStep technicalErrorStep = mock(TechnicalErrorStep.class);
        DataSource dataSource = mock(DataSource.class);
        Connection connection = mock(Connection.class);

        when(dataSource.getConnection()).thenReturn(connection);
        when(getClientLinksStep.execute(any(OperationContext.class))).thenReturn(4);
        when(noLinksFoundStep.getErrorCategory()).thenReturn("BUSINESS");
        when(noLinksFoundStep.getErrorNumber()).thenReturn("404");

        GetClientLinksOpService service = new GetClientLinksOpService(
                getClientLinksStep,
                noLinksFoundStep,
                databaseErrorStep,
                technicalErrorStep,
                dataSource
        );

        GetClientLinksRequestXml requestXml = new GetClientLinksRequestXml();
        requestXml.clientId = "C12345";
        requestXml.bankId = "1";

        String result = service.execute(requestXml);

        assertNotNull(result);
        assertTrue(result.contains("404") || result.contains("BUSINESS"));

        verify(getClientLinksStep).execute(any(OperationContext.class));
        verify(noLinksFoundStep).execute(any(OperationContext.class));
        verify(noLinksFoundStep).getErrorCategory();
        verify(noLinksFoundStep).getErrorNumber();
        verifyNoInteractions(databaseErrorStep);
        verifyNoInteractions(technicalErrorStep);
    }
}
