package il.co.dcd.integration;

import java.io.IOException;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ResourceLoader;

/** Import once per microservice; operation and step factories remain per invocation. */
@Configuration(proxyBeanMethods = false)
@EnableConfigurationProperties(NativeRuntimeProperties.class)
public class NativeRuntimeConfiguration {
    @Bean(destroyMethod = "close") @ConditionalOnMissingBean(DatabaseRegistry.class)
    public PooledDatabaseRegistry databaseRegistry(NativeRuntimeProperties properties) {
        return new PooledDatabaseRegistry(properties);
    }
    @Bean public DatabaseExecution databaseExecution(DatabaseRegistry registry) { return new DatabaseExecution(registry); }
    @Bean public OperationContextFactory operationContextFactory(ResourceLoader loader,
            NativeRuntimeProperties properties) throws IOException { return new OperationContextFactory(loader, properties); }
}
