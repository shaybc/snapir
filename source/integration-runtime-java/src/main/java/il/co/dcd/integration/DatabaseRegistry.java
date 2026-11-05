package il.co.dcd.integration;

import javax.sql.DataSource;

/** Resolves an exact deployment-owned database name; never substitutes another name. */
public interface DatabaseRegistry {
    DataSource resolve(String database);
}
