package example;

import java.sql.CallableStatement;
import java.sql.Connection;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

/** Infrastructure contract example: no database connection or handwritten JDBC implementation. */
public class AdapterContractTest {
    @Test void adapterPassesTheIdentifierToItsDependency() throws Exception {
        Connection connection = mock(Connection.class);
        CallableStatement statement = mock(CallableStatement.class);
        when(connection.prepareCall("{call sample(?)}")).thenReturn(statement);
        when(statement.getString(1)).thenReturn("sample-result");
        try (CallableStatement call = connection.prepareCall("{call sample(?)}")) {
            call.setString(1, "sample-id");
            call.execute();
            assertEquals("sample-result", call.getString(1));
        }
        verify(statement).setString(1, "sample-id");
        verify(statement).execute();
        verify(statement).close();
    }
}
