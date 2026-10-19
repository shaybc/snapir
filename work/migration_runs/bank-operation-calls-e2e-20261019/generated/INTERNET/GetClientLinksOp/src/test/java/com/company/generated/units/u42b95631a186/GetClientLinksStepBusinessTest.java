package com.company.generated.units.u42b95631a186;

import com.company.generated.units.u3a42c4326e3d.OperationContext;
import org.junit.jupiter.api.Test;

import java.sql.CallableStatement;
import java.sql.Connection;
import java.sql.ResultSet;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

public class GetClientLinksStepBusinessTest {

    @Test
    public void returnsSuccessAndSetsLinksOnValidResultSet() throws Exception {
        OperationContext context = new OperationContext();
        context.setValueAt("ClientId", "C123");
        context.setValueAt("BankId", "B1");

        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        ResultSet resultSet = mock(ResultSet.class);

        when(connection.prepareCall("{call PKG_PORTAL.GET_CLIENT_LINKS(?,?,?,?)}")).thenReturn(statement);
        when(statement.getString(3)).thenReturn("OK");
        when(statement.getObject(4)).thenReturn(resultSet);
        when(resultSet.next()).thenReturn(true).thenReturn(false);
        when(resultSet.getString("LINK_ID")).thenReturn("L1");
        when(resultSet.getString("LINK_URL")).thenReturn("http://example.com");
        when(resultSet.getString("IS_EXTERNAL")).thenReturn("Y");
        when(resultSet.getString("ICON_CODE")).thenReturn("icon-1");

        context.setConnection(connection);

        GetClientLinksStep step = new GetClientLinksStep();
        int rc = step.execute(context);

        assertEquals(GetClientLinksStep.RC_SUCCESS, rc);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> links = (List<Map<String, Object>>) context.getValueAt("Links");
        assertNotNull(links);
        assertEquals(1, links.size());
        assertEquals("L1", links.get(0).get("LinkId"));
        assertEquals(true, links.get(0).get("IsExternal"));

        verify(statement).setString(1, "C123");
        verify(statement).setString(2, "B1");
        verify(statement).execute();
    }

    @Test
    public void returnsNotFoundWhenSpRcIsNotFound() throws Exception {
        OperationContext context = new OperationContext();
        context.setValueAt("ClientId", "C123");
        context.setValueAt("BankId", "B1");

        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);

        when(connection.prepareCall(anyString())).thenReturn(statement);
        when(statement.getString(3)).thenReturn("NOT_FOUND");

        context.setConnection(connection);

        GetClientLinksStep step = new GetClientLinksStep();
        int rc = step.execute(context);

        assertEquals(GetClientLinksStep.RC_NOT_FOUND, rc);
    }

    @Test
    public void returnsDbErrorOnException() throws Exception {
        OperationContext context = new OperationContext();
        context.setValueAt("ClientId", "C123");
        context.setValueAt("BankId", "B1");

        Connection connection = mock(Connection.class);
        when(connection.prepareCall(anyString())).thenThrow(new RuntimeException("DB down"));

        context.setConnection(connection);

        GetClientLinksStep step = new GetClientLinksStep();
        int rc = step.execute(context);

        assertEquals(GetClientLinksStep.RC_DB_ERROR, rc);
        assertEquals("DB down", context.getValueAt("DatabaseError"));
    }
}
