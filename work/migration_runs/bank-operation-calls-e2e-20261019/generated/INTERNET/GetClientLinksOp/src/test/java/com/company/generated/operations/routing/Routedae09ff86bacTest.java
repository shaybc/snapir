package com.company.generated.operations.routing;

import com.company.generated.operations.GetClientLinksOpService;
import com.company.generated.units.u3a42c4326e3d.DatabaseErrorStep;
import com.company.generated.units.u3643d2141e0a.NoLinksFoundStep;
import com.company.generated.units.u42b95631a186.GetClientLinksStep;
import com.company.generated.units.u561a01497abb.GetClientLinksRequestXml;
import com.company.generated.units.u9d214a54d7b1.TechnicalErrorStep;
import org.junit.jupiter.api.Test;

import javax.sql.DataSource;
import java.sql.Connection;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.*;

public class Routedae09ff86bacTest {

    @Test
    public void executesTechnicalErrorRouteWhenUnexpectedReturnCodeOccurs() throws Exception {
        GetClientLinksStep getClientLinksStep = mock(GetClientLinksStep.class);
        NoLinksFoundStep noLinksFoundStep = mock(NoLinksFoundStep.class);
        DatabaseErrorStep databaseErrorStep = mock(DatabaseErrorStep.class);
        TechnicalErrorStep technicalErrorStep = mock(TechnicalErrorStep.class);
        DataSource dataSource = mock(DataSource.class);
        Connection connection = mock(Connection.class);

        when(dataSource.getConnection()).thenReturn(connection);
        when(getClientLinksStep.execute(any())).thenReturn(99); // unexpected return code triggering onOtherDo -> TechnicalError
        when(technicalErrorStep.getErrorCategory()).thenReturn("TECH");
        when(technicalErrorStep.getErrorNumber()).thenReturn("500");

        GetClientLinksOpService service = new GetClientLinksOpService(
                getClientLinksStep,
                noLinksFoundStep,
                databaseErrorStep,
                technicalErrorStep,
                dataSource
        );

        GetClientLinksRequestXml requestXml = new GetClientLinksRequestXml();
        requestXml.clientId = "123456";
        requestXml.bankId = "01";

        String result = service.execute(requestXml);

        assertNotNull(result);
        assertTrue(result.contains("TECH"));
        assertTrue(result.contains("500"));

        verify(getClientLinksStep).execute(any());
        verify(technicalErrorStep).execute(any());
        verifyNoInteractions(noLinksFoundStep);
        verifyNoInteractions(databaseErrorStep);
        verify(connection).close();
    }
}
