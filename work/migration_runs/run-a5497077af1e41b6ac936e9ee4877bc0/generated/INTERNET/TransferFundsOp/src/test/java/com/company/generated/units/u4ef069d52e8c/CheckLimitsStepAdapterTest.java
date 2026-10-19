package com.company.generated.units.u4ef069d52e8c;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.Types;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

public class CheckLimitsStepAdapterTest {

    @Test
    public void adapterPassesParametersAndRegistersOutParametersCorrectly() throws Exception {
        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        when(connection.prepareCall("{call PKG_TRANSFERS.VALIDATE_LIMITS(?,?,?,?,?,?)}")).thenReturn(statement);
        when(statement.getString(4)).thenReturn("SUCCESS");

        try (CallableStatement call = connection.prepareCall("{call PKG_TRANSFERS.VALIDATE_LIMITS(?,?,?,?,?,?)}")) {
            call.setString(1, "ACC-789");
            call.setBigDecimal(2, new BigDecimal("250.00"));
            call.setString(3, "CLI-111");
            call.registerOutParameter(4, Types.VARCHAR);
            call.registerOutParameter(5, Types.NUMERIC);
            call.registerOutParameter(6, Types.NUMERIC);
            call.execute();
            assertEquals("SUCCESS", call.getString(4));
        }

        verify(statement).setString(1, "ACC-789");
        verify(statement).setBigDecimal(2, new BigDecimal("250.00"));
        verify(statement).setString(3, "CLI-111");
        verify(statement).registerOutParameter(4, Types.VARCHAR);
        verify(statement).registerOutParameter(5, Types.NUMERIC);
        verify(statement).registerOutParameter(6, Types.NUMERIC);
        verify(statement).execute();
    }
}
