package il.co.dcd.integration;

import javax.sql.DataSource;
import java.sql.Connection;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class DatabaseExecutionTest {
    @Test void releasesOnSuccessAndException() throws Exception {
        DataSource source = mock(DataSource.class); Connection connection = mock(Connection.class);
        when(source.getConnection()).thenReturn(connection);
        DatabaseExecution executor = new DatabaseExecution(name -> source);
        assertEquals("value", executor.execute("selected", c -> { assertSame(connection, c); return "value"; }));
        assertThrows(Exception.class, () -> executor.execute("selected", c -> { throw new Exception("failure"); }));
        verify(connection, times(2)).close(); verify(connection, never()).commit(); verify(connection, never()).rollback();
    }
    @Test void explicitTransactionCommitsAndRollbackPredicateControlsOutcome() throws Exception {
        DataSource source = mock(DataSource.class); Connection connection = mock(Connection.class);
        when(source.getConnection()).thenReturn(connection); when(connection.getAutoCommit()).thenReturn(true);
        DatabaseExecution executor = new DatabaseExecution(name -> source);
        assertEquals(Integer.valueOf(0), executor.<Integer>inTransaction("default", c -> 0, code -> code != 0));
        verify(connection).commit(); verify(connection).close();
        reset(connection); when(connection.getAutoCommit()).thenReturn(true);
        assertEquals(Integer.valueOf(8), executor.<Integer>inTransaction("default", c -> 8, code -> code != 0));
        verify(connection).rollback(); verify(connection, never()).commit(); verify(connection).close();
    }
    @Test void checkedExceptionRollsBackAndReleasesConnection() throws Exception {
        DataSource source = mock(DataSource.class); Connection connection = mock(Connection.class);
        when(source.getConnection()).thenReturn(connection); when(connection.getAutoCommit()).thenReturn(true);
        DatabaseExecution executor = new DatabaseExecution(name -> source);
        assertThrows(Exception.class, () -> executor.inTransaction("default", c -> { throw new Exception("failure"); }, value -> false));
        verify(connection).rollback(); verify(connection).close();
    }
    @Test void unknownNameNeverFallsBack() {
        NativeRuntimeProperties properties = new NativeRuntimeProperties();
        assertThrows(IllegalArgumentException.class, () -> new PooledDatabaseRegistry(properties));
    }
}
