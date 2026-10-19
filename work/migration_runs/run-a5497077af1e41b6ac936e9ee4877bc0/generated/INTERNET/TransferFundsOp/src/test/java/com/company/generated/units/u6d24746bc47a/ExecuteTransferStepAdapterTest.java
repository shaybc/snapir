package com.company.generated.units.u6d24746bc47a;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.Types;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

public class ExecuteTransferStepAdapterTest {

    @Test
    public void adapterPreparesAndExecutesStoredProcedureWithParameters() throws Exception {
        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        when(connection.prepareCall(anyString())).thenReturn(statement);
        when(statement.getString(6)).thenReturn("SUCCESS");
        when(statement.getString(7)).thenReturn("TRX-123");
        when(statement.getString(8)).thenReturn("COMPLETED");
        when(statement.getDate(9)).thenReturn(new java.sql.Date(System.currentTimeMillis()));
        when(statement.getBigDecimal(10)).thenReturn(new BigDecimal("900.00"));

        Map<String, Object> context = new HashMap<>();
        context.put("Connection", connection);
        context.put("SourceAccount", "ACC-100");
        context.put("TargetAccount", "ACC-200");
        context.put("Amount", new BigDecimal("100.00"));
        context.put("Currency", "USD");
        context.put("TransferReference", "REF-999");

        ExecuteTransferStep step = new ExecuteTransferStep();
        int result = step.execute(context);

        assertEquals(ExecuteTransferStep.RC_SUCCESS, result);
        assertEquals("TRX-123", context.get("TransferId"));
        assertEquals("COMPLETED", context.get("TransferStatus"));
        verify(statement).setString(1, "ACC-100");
        verify(statement).setString(2, "ACC-200");
        verify(statement).setBigDecimal(3, new BigDecimal("100.00"));
        verify(statement).setString(4, "USD");
        verify(statement).setString(5, "REF-999");
        verify(statement).execute();
    }
}
