package com.company.generated.units.u42b95631a186;

import org.junit.jupiter.api.Test;

import java.sql.CallableStatement;
import java.sql.Connection;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

public class GetClientLinksAdapterContractTest {

    @Test
    public void verifiesCallableStatementContract() throws Exception {
        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        when(connection.prepareCall("{call PKG_PORTAL.GET_CLIENT_LINKS(?,?,?,?)}")).thenReturn(statement);
        when(statement.getString(3)).thenReturn("SUCCESS");

        try (CallableStatement call = connection.prepareCall("{call PKG_PORTAL.GET_CLIENT_LINKS(?,?,?,?)}")) {
            call.setString(1, "client-1");
            call.setString(2, "bank-1");
            call.registerOutParameter(3, java.sql.Types.VARCHAR);
            call.registerOutParameter(4, java.sql.Types.REF_CURSOR);
            call.execute();
            assertEquals("SUCCESS", call.getString(3));
        }

        verify(statement).setString(1, "client-1");
        verify(statement).setString(2, "bank-1");
        verify(statement).execute();
        verify(statement).close();
    }
}
