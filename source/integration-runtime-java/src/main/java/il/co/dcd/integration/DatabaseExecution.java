package il.co.dcd.integration;

import java.sql.Connection;
import java.util.function.Predicate;
import javax.sql.DataSource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.datasource.DataSourceUtils;
import org.springframework.jdbc.support.JdbcTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

/** Centralizes transaction-aware connection lifetime without changing native business outcomes. */
public final class DatabaseExecution {
    private static final Logger LOG = LoggerFactory.getLogger(DatabaseExecution.class);
    private final DatabaseRegistry registry;
    public DatabaseExecution(DatabaseRegistry registry) { this.registry = registry; }
    @FunctionalInterface public interface Work<T> { T run(Connection connection) throws Exception; }

    /** Preserve source transaction behavior and always release the borrowed connection. */
    public <T> T execute(String database, Work<T> work) throws Exception {
        DataSource source = registry.resolve(database);
        Connection connection = DataSourceUtils.getConnection(source);
        long started = System.nanoTime();
        try { return work.run(connection); }
        finally {
            DataSourceUtils.releaseConnection(connection, source);
            LOG.debug("Database invocation completed; database={}, elapsedMs={}", database,
                    (System.nanoTime() - started) / 1000000);
        }
    }

    /** Explicit opt-in transaction with a caller-supplied, source-backed failure-outcome policy. */
    public <T> T inTransaction(String database, Work<T> work, Predicate<T> rollback) throws Exception {
        TransactionTemplate template = new TransactionTemplate(new JdbcTransactionManager(registry.resolve(database)));
        try {
            return template.execute(status -> {
                try {
                    T result = execute(database, work);
                    if (rollback.test(result)) status.setRollbackOnly();
                    return result;
                } catch (Exception error) { throw new WorkFailure(error); }
            });
        } catch (WorkFailure error) { throw (Exception) error.getCause(); }
    }
    private static final class WorkFailure extends RuntimeException {
        WorkFailure(Exception cause) { super(cause); }
    }
}
