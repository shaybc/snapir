package com.company.generated.units.u6d24746bc47a;

import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

public class ExecuteTransferStepBusinessTest {

    @Test
    public void returnsRejectedWhenCoreBankingRejects() throws Exception {
        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        when(connection.prepareCall(anyString())).thenReturn(statement);
        when(statement.getString(6)).thenReturn("REJECTED");

        Map<String, Object> context = new HashMap<>();
        context.put("Connection", connection);
        context.put("SourceAccount", "ACC-100");
        context.put("TargetAccount", "ACC-200");
        context.put("Amount", new BigDecimal("100.00"));

        ExecuteTransferStep step = new ExecuteTransferStep();
        int result = step.execute(context);

        assertEquals(ExecuteTransferStep.RC_REJECTED, result);
    }

    @Test
    public void returnsDuplicateWhenReferenceExists() throws Exception {
        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        when(connection.prepareCall(anyString())).thenReturn(statement);
        when(statement.getString(6)).thenReturn("DUPLICATE");

        Map<String, Object> context = new HashMap<>();
        context.put("Connection", connection);
        context.put("SourceAccount", "ACC-100");
        context.put("TargetAccount", "ACC-200");
        context.put("Amount", new BigDecimal("100.00"));

        ExecuteTransferStep step = new ExecuteTransferStep();
        int result = step.execute(context);

        assertEquals(ExecuteTransferStep.RC_DUPLICATE, result);
    }

    @Test
    public void returnsDbErrorAndPopulatesContextWhenExceptionOccurs() throws Exception {
        Connection connection = mock(Connection.class);
        when(connection.prepareCall(anyString())).thenThrow(new RuntimeException("Connection lost"));

        Map<String, Object> context = new HashMap<>();
        context.put("Connection", connection);

        ExecuteTransferStep step = new ExecuteTransferStep();
        int result = step.execute(context);

        assertEquals(ExecuteTransferStep.RC_DB_ERROR, result);
        assertEquals("Connection lost", context.get("DatabaseError"));
    }
}
