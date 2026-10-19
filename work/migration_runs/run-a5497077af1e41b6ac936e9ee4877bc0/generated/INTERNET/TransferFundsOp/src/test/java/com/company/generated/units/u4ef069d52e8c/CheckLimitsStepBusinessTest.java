package com.company.generated.units.u4ef069d52e8c;

import org.junit.jupiter.api.Test;
import java.math.BigDecimal;
import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.Types;
import java.util.HashMap;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

public class CheckLimitsStepBusinessTest {

    @Test
    public void testSuccessRouting() throws Exception {
        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        when(connection.prepareCall(anyString())).thenReturn(statement);
        when(statement.getString(4)).thenReturn("SUCCESS");

        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "ACC-123");
        context.put("Amount", new BigDecimal("150.00"));
        context.put("ClientId", "CLI-999");
        context.put("Connection", connection);

        CheckLimitsStep step = new CheckLimitsStep();
        int result = step.execute(context);

        assertEquals(0, result);
        verify(statement).execute();
    }

    @Test
    public void testLimitExceededRouting() throws Exception {
        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        when(connection.prepareCall(anyString())).thenReturn(statement);
        when(statement.getString(4)).thenReturn("LIMIT_EXCEEDED");
        when(statement.getBigDecimal(5)).thenReturn(new BigDecimal("500.00"));
        when(statement.getBigDecimal(6)).thenReturn(new BigDecimal("5000.00"));

        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "ACC-123");
        context.put("Amount", new BigDecimal("1500.00"));
        context.put("ClientId", "CLI-999");
        context.put("Connection", connection);

        CheckLimitsStep step = new CheckLimitsStep();
        int result = step.execute(context);

        assertEquals(3, result);
        assertEquals(new BigDecimal("500.00"), context.get("DailyRemaining"));
        assertEquals(new BigDecimal("5000.00"), context.get("DailyLimit"));
    }

    @Test
    public void testInsufficientFundsRouting() throws Exception {
        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        when(connection.prepareCall(anyString())).thenReturn(statement);
        when(statement.getString(4)).thenReturn("INSUFFICIENT");

        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "ACC-123");
        context.put("Amount", new BigDecimal("15000.00"));
        context.put("ClientId", "CLI-999");
        context.put("Connection", connection);

        CheckLimitsStep step = new CheckLimitsStep();
        int result = step.execute(context);

        assertEquals(4, result);
    }

    @Test
    public void testNotEligibleRouting() throws Exception {
        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        when(connection.prepareCall(anyString())).thenReturn(statement);
        when(statement.getString(4)).thenReturn("NOT_ELIGIBLE");

        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "ACC-123");
        context.put("Amount", new BigDecimal("50.00"));
        context.put("ClientId", "CLI-999");
        context.put("Connection", connection);

        CheckLimitsStep step = new CheckLimitsStep();
        int result = step.execute(context);

        assertEquals(5, result);
    }

    @Test
    public void testDatabaseErrorRouting() throws Exception {
        Connection connection = mock(Connection.class);
        when(connection.prepareCall(anyString())).thenThrow(new RuntimeException("DB Connection Down"));

        Map<String, Object> context = new HashMap<>();
        context.put("SourceAccount", "ACC-123");
        context.put("Amount", new BigDecimal("50.00"));
        context.put("ClientId", "CLI-999");
        context.put("Connection", connection);

        CheckLimitsStep step = new CheckLimitsStep();
        int result = step.execute(context);

        assertEquals(8, result);
        assertEquals("DB Connection Down", context.get("DatabaseError"));
    }
}
