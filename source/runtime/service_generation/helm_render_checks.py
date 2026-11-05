"""Check Helm's rendered effective database/sidecar settings against typed ordered values."""


def validate_rendered_configuration(pod,container,runtime,spec):
    """Reject mismatched driver, credentials, pool or chart-only orchestration leakage."""
    if spec.operation.database:
        name=spec.operation.database;db=spec.databases[name];actual=runtime['databases'][name]
        expected={'jdbc-url':db.jdbcUrl,'driver-class':db.driverClass,'username':'${NATIVE_DATABASE_USERNAME}',
            'password':'${NATIVE_DATABASE_PASSWORD}','minimum-idle':db.pool.minimumIdle,
            'maximum-pool-size':db.pool.maximumPoolSize,'connection-timeout-ms':db.pool.connectionTimeoutMs,
            'max-lifetime-ms':db.pool.maxLifetimeMs}
        if actual!=expected:raise ValueError('Helm effective JDBC settings differ from validated overlay merge')
        env={v['name']:v for v in container['env']}
        for variable,key in [('NATIVE_DATABASE_USERNAME',db.credentialsSecret.usernameKey),('NATIVE_DATABASE_PASSWORD',db.credentialsSecret.passwordKey)]:
            if env[variable]['valueFrom']['secretKeyRef']!={'name':db.credentialsSecret.name,'key':key}:
                raise ValueError('Helm database credential Secret reference changed')
    demo=spec.demoInfrastructure;sidecars=[c for c in pod['spec']['containers'] if c['name']=='fixture-server']
    if not demo or not demo.enabled:
        if sidecars:raise ValueError('Production rendering contains a fixture server')
        return
    if len(sidecars)!=1:raise ValueError('Demo fixture server sidecar missing')
    sidecar=sidecars[0]
    mount=next(v for v in sidecar['volumeMounts'] if v['name']=='fixture-data')
    volume=next(v for v in pod['spec']['volumes'] if v['name']=='fixture-data')
    if not mount.get('readOnly') or not volume['persistentVolumeClaim'].get('readOnly'):
        raise ValueError('Fixture data must remain read-only')
    if 'demoInfrastructure' in runtime or 'demo' in runtime:
        raise ValueError('Demo orchestration leaked into application configuration')
