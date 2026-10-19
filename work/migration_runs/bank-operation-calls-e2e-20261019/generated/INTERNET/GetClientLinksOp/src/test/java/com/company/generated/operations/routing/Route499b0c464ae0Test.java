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
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

public class Route499b0c464ae0Test {

    @Test
    void testGetClientLinksDatabaseErrorRoute() throws Exception {
        GetClientLinksStep getClientLinksStep = mock(GetClientLinksStep.class);
        NoLinksFoundStep noLinksFoundStep = mock(NoLinksFoundStep.class);
        DatabaseErrorStep databaseErrorStep = mock(DatabaseErrorStep.class);
        TechnicalErrorStep technicalErrorStep = mock(TechnicalErrorStep.class);
        DataSource dataSource = mock(DataSource.class);
        Connection connection = mock(Connection.class);

        when(dataSource.getConnection()).thenReturn(connection);
        when(getClientLinksStep.execute(any())).thenReturn(8);
        when(databaseErrorStep.getErrorCategory()).thenReturn("DB_ERROR_CAT");
        when(databaseErrorStep.getErrorNumber()).thenReturn("8000");

        GetClientLinksOpService service = new GetClientLinksOpService(
                getClientLinksStep,
                noLinksFoundStep,
                databaseErrorStep,
                technicalErrorStep,
                dataSource
        );

        GetClientLinksRequestXml requestXml = new GetClientLinksRequestXml();
        requestXml.clientId = "client-123";
        requestXml.bankId = "bank-1";

        String result = service.execute(requestXml);

        assertNotNull(result);
        verify(getClientLinksStep).execute(any());
        verify(databaseErrorStep).execute(any());
        verifyNoInteractions(noLinksFoundStep);
        verifyNoInteractions(technicalErrorStep);
        verify(connection).close();
    }
}
