## Operation: TransferFundsOp

### Summary
Generated candidate for channel INTERNET; production readiness requires Gate 4.

### Conversion notes
- Routing: {"ValidateTransfer": {"on0Do": "CheckLimits", "onOtherDo": "ValidationFailed"}, "CheckLimits": {"on0Do": "FraudCheck", "on3Do": "DailyLimitExceeded", "on4Do": "InsufficientFunds", "on5Do": "AccountNotEligible", "on8Do": "DatabaseError", "onOtherDo": "TechnicalError"}, "FraudCheck": {"on0Do": "ExecuteTransfer", "on2Do": "FraudSuspected", "onOtherDo": "TechnicalError", "onTimeoutDo": "SkipFraudOnTimeout"}, "SkipFraudOnTimeout": {"on0Do": "ExecuteTransfer", "onOtherDo": "TechnicalError"}, "ExecuteTransfer": {"on0Do": "end", "on6Do": "CoreBankingRejected", "on7Do": "TransferAlreadyProcessed", "on8Do": "DatabaseError", "onOtherDo": "TechnicalError"}, "ValidationFailed": {"onOtherDo": "end"}, "InsufficientFunds": {"onOtherDo": "end"}, "DailyLimitExceeded": {"onOtherDo": "end"}, "AccountNotEligible": {"onOtherDo": "end"}, "FraudSuspected": {"onOtherDo": "end"}, "CoreBankingRejected": {"onOtherDo": "end"}, "TransferAlreadyProcessed": {"onOtherDo": "end"}, "DatabaseError": {"onOtherDo": "end"}, "TechnicalError": {"onOtherDo": "end"}}
- Shared components: None
- Source XML length: 7206 characters

### Validation results
- Build passed: True
- Tests passed: True
- XML compatibility passed: False
- IBM guard passed: True
- Behavioral equivalence passed: False
- Failure class: none

### Files generated
- services\INTERNET\TransferFundsOp\dependency_audit.jsonl
- services\INTERNET\TransferFundsOp\pom.xml
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\Application.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\config\ProductionConfiguration.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\config\XmlMessageConverterConfig.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\controller\TransferFundsController.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\error\GlobalExceptionHandler.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\operations\TransferFundsOpService.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u06cdcaacb2a8\CoreBankingRejectedStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u1bde9d232fc4\DailyLimitExceededStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u1e4c733765f0\AccountNotEligibleStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u3edad4d894ed\SkipFraudOnTimeoutStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u4ef069d52e8c\CheckLimitsStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u5ce9c9ef500c\TransferFundsRequestBusiness.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u5ce9c9ef500c\TransferFundsRequestMapper.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u5ce9c9ef500c\TransferFundsRequestXml.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u66bf2c108225\ErrorReply.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u66bf2c108225\ErrorReplyXml.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u66bf2c108225\StandardErrorRSFmtMapper.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u6d24746bc47a\ExecuteTransferStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u87dd336469df\InsufficientFundsStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\u90e3461e522a\FraudSuspectedStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\ub5afca9c05e0\TransferFundsResponseBusiness.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\ub5afca9c05e0\TransferFundsResponseMapper.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\ub5afca9c05e0\TransferFundsResponseXml.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\ub9a6a73909a9\TransferAlreadyProcessedStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\udb5b1a29f676\ValidateTransferStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\uf2c8754a25a6\FraudCheckStep.java
- services\INTERNET\TransferFundsOp\src\main\java\com\company\generated\units\uf2c8754a25a6\FraudDetectionServicePort.java
- services\INTERNET\TransferFundsOp\src\main\resources\application.properties
- services\INTERNET\TransferFundsOp\src\test\java\com\company\generated\wiring\StartupWiringTest.java
- services\INTERNET\TransferFundsOp\target\classes\application.properties
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\Application.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\config\ProductionConfiguration.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\config\XmlMessageConverterConfig.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\controller\TransferFundsController.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\error\GlobalExceptionHandler.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\operations\TransferFundsOpService.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u06cdcaacb2a8\CoreBankingRejectedStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u1bde9d232fc4\DailyLimitExceededStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u1e4c733765f0\AccountNotEligibleStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u3edad4d894ed\SkipFraudOnTimeoutStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u4ef069d52e8c\CheckLimitsStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u5ce9c9ef500c\TransferFundsRequestBusiness.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u5ce9c9ef500c\TransferFundsRequestMapper.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u5ce9c9ef500c\TransferFundsRequestXml.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u66bf2c108225\ErrorReply.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u66bf2c108225\ErrorReplyXml.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u66bf2c108225\StandardErrorRSFmtMapper.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u6d24746bc47a\ExecuteTransferStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u87dd336469df\InsufficientFundsStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\u90e3461e522a\FraudSuspectedStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\ub5afca9c05e0\TransferFundsResponseBusiness.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\ub5afca9c05e0\TransferFundsResponseMapper.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\ub5afca9c05e0\TransferFundsResponseXml$NullableBoolean.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\ub5afca9c05e0\TransferFundsResponseXml.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\ub9a6a73909a9\TransferAlreadyProcessedStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\udb5b1a29f676\ValidateTransferStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\uf2c8754a25a6\FraudCheckStep.class
- services\INTERNET\TransferFundsOp\target\classes\com\company\generated\units\uf2c8754a25a6\FraudDetectionServicePort.class
- services\INTERNET\TransferFundsOp\target\maven-archiver\pom.properties
- services\INTERNET\TransferFundsOp\target\maven-status\maven-compiler-plugin\compile\default-compile\createdFiles.lst
- services\INTERNET\TransferFundsOp\target\maven-status\maven-compiler-plugin\compile\default-compile\inputFiles.lst
- services\INTERNET\TransferFundsOp\target\maven-status\maven-compiler-plugin\testCompile\default-testCompile\createdFiles.lst
- services\INTERNET\TransferFundsOp\target\maven-status\maven-compiler-plugin\testCompile\default-testCompile\inputFiles.lst
- services\INTERNET\TransferFundsOp\target\surefire-reports\com.company.generated.wiring.StartupWiringTest.txt
- services\INTERNET\TransferFundsOp\target\surefire-reports\TEST-com.company.generated.wiring.StartupWiringTest.xml
- services\INTERNET\TransferFundsOp\target\test-classes\com\company\generated\wiring\StartupWiringTest.class
- services\INTERNET\TransferFundsOp\target\TransferFundsOp-1.0.0-cdbfffbd6243.jar
- services\INTERNET\TransferFundsOp\target\TransferFundsOp-1.0.0-cdbfffbd6243.jar.original

### Known issues
- None

## Evidence and blockers
{
  "validation": {
    "ibm_guard_passed": true,
    "findings": [],
    "build_passed": true,
    "test_status": "passed",
    "package_passed": true,
    "xml_compatibility": "not_available",
    "behavioral_equivalence": "not_available",
    "legacy_trace_comparison": "not_available",
    "compile_log": {
      "stdout": "[INFO] Scanning for projects...\n[INFO] \n[INFO] ---------------< com.company.migration:TransferFundsOp >----------------\n[INFO] Building TransferFundsOp 1.0.0-cdbfffbd6243\n[INFO]   from pom.xml\n[INFO] --------------------------------[ jar ]---------------------------------\n[INFO] \n[INFO] --- enforcer:3.6.2:enforce (default) @ TransferFundsOp ---\n[INFO] Rule 0: org.apache.maven.enforcer.rules.version.RequireJavaVersion passed\n[INFO] \n[INFO] --- resources:3.4.0:resources (default-resources) @ TransferFundsOp ---\n[INFO] Copying 1 resource from src\\main\\resources to target\\classes\n[INFO] \n[INFO] --- compiler:3.14.1:compile (default-compile) @ TransferFundsOp ---\n[INFO] Recompiling the module because of changed source code.\n[INFO] Compiling 27 source files with javac [debug release 25] to target\\classes\n[INFO] /C:/GitHub/shaybc/snapir/work/migration_runs/run-a5497077af1e41b6ac936e9ee4877bc0/services/INTERNET/TransferFundsOp/src/main/java/com/company/generated/units/u66bf2c108225/StandardErrorRSFmtMapper.java: C:\\GitHub\\shaybc\\snapir\\work\\migration_runs\\run-a5497077af1e41b6ac936e9ee4877bc0\\services\\INTERNET\\TransferFundsOp\\src\\main\\java\\com\\company\\generated\\units\\u66bf2c108225\\StandardErrorRSFmtMapper.java uses or overrides a deprecated API.\n[INFO] /C:/GitHub/shaybc/snapir/work/migration_runs/run-a5497077af1e41b6ac936e9ee4877bc0/services/INTERNET/TransferFundsOp/src/main/java/com/company/generated/units/u66bf2c108225/StandardErrorRSFmtMapper.java: Recompile with -Xlint:deprecation for details.\n[INFO] ------------------------------------------------------------------------\n[INFO] BUILD SUCCESS\n[INFO] ------------------------------------------------------------------------\n[INFO] Total time:  4.515 s\n[INFO] Finished at: 2026-10-12T03:48:03+03:00\n[INFO] ------------------------------------------------------------------------\n",
      "stderr": ""
    },
    "test_log": {
      "stdout": "[INFO] Scanning for projects...\n[INFO] \n[INFO] ---------------< com.company.migration:TransferFundsOp >----------------\n[INFO] Building TransferFundsOp 1.0.0-cdbfffbd6243\n[INFO]   from pom.xml\n[INFO] --------------------------------[ jar ]---------------------------------\n[INFO] Downloading from central: https://repo.maven.apache.org/maven2/org/checkerframework/checker-qual/3.48.3/checker-qual-3.48.3.jar\n[INFO] Downloaded from central: https://repo.maven.apache.org/maven2/org/checkerframework/checker-qual/3.48.3/checker-qual-3.48.3.jar (239 kB at 350 kB/s)\n[INFO] \n[INFO] --- enforcer:3.6.2:enforce (default) @ TransferFundsOp ---\n[INFO] Rule 0: org.apache.maven.enforcer.rules.version.RequireJavaVersion passed\n[INFO] \n[INFO] --- resources:3.4.0:resources (default-resources) @ TransferFundsOp ---\n[INFO] Copying 1 resource from src\\main\\resources to target\\classes\n[INFO] \n[INFO] --- compiler:3.14.1:compile (default-compile) @ TransferFundsOp ---\n[INFO] Nothing to compile - all classes are up to date.\n[INFO] \n[INFO] --- resources:3.4.0:testResources (default-testResources) @ TransferFundsOp ---\n[INFO] skip non existing resourceDirectory C:\\GitHub\\shaybc\\snapir\\work\\migration_runs\\run-a5497077af1e41b6ac936e9ee4877bc0\\services\\INTERNET\\TransferFundsOp\\src\\test\\resources\n[INFO] \n[INFO] --- compiler:3.14.1:testCompile (default-testCompile) @ TransferFundsOp ---\n[INFO] Recompiling the module because of changed dependency.\n[INFO] Compiling 1 source file with javac [debug release 25] to target\\test-classes\n[INFO] \n[INFO] --- surefire:3.5.4:test (default-test) @ TransferFundsOp ---\n[INFO] Using auto detected provider org.apache.maven.surefire.junitplatform.JUnitPlatformProvider\n[INFO] \n[INFO] -------------------------------------------------------\n[INFO]  T E S T S\n[INFO] -------------------------------------------------------\n[INFO] Running com.company.generated.wiring.StartupWiringTest\n[INFO] Tests run: 1, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 2.877 s -- in com.company.generated.wiring.StartupWiringTest\n[INFO] \n[INFO] Results:\n[INFO] \n[INFO] Tests run: 1, Failures: 0, Errors: 0, Skipped: 0\n[INFO] \n[INFO] ------------------------------------------------------------------------\n[INFO] BUILD SUCCESS\n[INFO] ------------------------------------------------------------------------\n[INFO] Total time:  9.735 s\n[INFO] Finished at: 2026-10-12T03:48:21+03:00\n[INFO] ------------------------------------------------------------------------\n",
      "stderr": "Mockito is currently self-attaching to enable the inline-mock-maker. This will no longer work in future releases of the JDK. Please add Mockito as an agent to your build as described in Mockito's documentation: https://javadoc.io/doc/org.mockito/mockito-core/latest/org.mockito/org/mockito/Mockito.html#0.3\nWARNING: A Java agent has been loaded dynamically (C:\\Users\\shayg\\.m2\\repository\\net\\bytebuddy\\byte-buddy-agent\\1.17.7\\byte-buddy-agent-1.17.7.jar)\nWARNING: If a serviceability tool is in use, please run with -XX:+EnableDynamicAgentLoading to hide this warning\nWARNING: If a serviceability tool is not in use, please run with -Djdk.instrument.traceUsage for more information\nWARNING: Dynamic loading of agents will be disallowed by default in a future release\nJava HotSpot(TM) 64-Bit Server VM warning: Sharing is only supported for boot loader classes because bootstrap classpath has been appended\n"
    },
    "test_count": 1,
    "package_log": {
      "stdout": "[INFO] Scanning for projects...\n[INFO] \n[INFO] ---------------< com.company.migration:TransferFundsOp >----------------\n[INFO] Building TransferFundsOp 1.0.0-cdbfffbd6243\n[INFO]   from pom.xml\n[INFO] --------------------------------[ jar ]---------------------------------\n[INFO] \n[INFO] --- enforcer:3.6.2:enforce (default) @ TransferFundsOp ---\n[INFO] Rule 0: org.apache.maven.enforcer.rules.version.RequireJavaVersion passed\n[INFO] \n[INFO] --- resources:3.4.0:resources (default-resources) @ TransferFundsOp ---\n[INFO] Copying 1 resource from src\\main\\resources to target\\classes\n[INFO] \n[INFO] --- compiler:3.14.1:compile (default-compile) @ TransferFundsOp ---\n[INFO] Nothing to compile - all classes are up to date.\n[INFO] \n[INFO] --- resources:3.4.0:testResources (default-testResources) @ TransferFundsOp ---\n[INFO] skip non existing resourceDirectory C:\\GitHub\\shaybc\\snapir\\work\\migration_runs\\run-a5497077af1e41b6ac936e9ee4877bc0\\services\\INTERNET\\TransferFundsOp\\src\\test\\resources\n[INFO] \n[INFO] --- compiler:3.14.1:testCompile (default-testCompile) @ TransferFundsOp ---\n[INFO] Nothing to compile - all classes are up to date.\n[INFO] \n[INFO] --- surefire:3.5.4:test (default-test) @ TransferFundsOp ---\n[INFO] Using auto detected provider org.apache.maven.surefire.junitplatform.JUnitPlatformProvider\n[INFO] \n[INFO] -------------------------------------------------------\n[INFO]  T E S T S\n[INFO] -------------------------------------------------------\n[INFO] Running com.company.generated.wiring.StartupWiringTest\n[INFO] Tests run: 1, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 2.699 s -- in com.company.generated.wiring.StartupWiringTest\n[INFO] \n[INFO] Results:\n[INFO] \n[INFO] Tests run: 1, Failures: 0, Errors: 0, Skipped: 0\n[INFO] \n[INFO] \n[INFO] --- jar:3.5.0:jar (default-jar) @ TransferFundsOp ---\n[INFO] Building jar: C:\\GitHub\\shaybc\\snapir\\work\\migration_runs\\run-a5497077af1e41b6ac936e9ee4877bc0\\services\\INTERNET\\TransferFundsOp\\target\\TransferFundsOp-1.0.0-cdbfffbd6243.jar\n[INFO] \n[INFO] --- spring-boot:3.5.16:repackage (default) @ TransferFundsOp ---\n[INFO] Replacing main artifact C:\\GitHub\\shaybc\\snapir\\work\\migration_runs\\run-a5497077af1e41b6ac936e9ee4877bc0\\services\\INTERNET\\TransferFundsOp\\target\\TransferFundsOp-1.0.0-cdbfffbd6243.jar with repackaged archive, adding nested dependencies in BOOT-INF/.\n[INFO] The original artifact has been renamed to C:\\GitHub\\shaybc\\snapir\\work\\migration_runs\\run-a5497077af1e41b6ac936e9ee4877bc0\\services\\INTERNET\\TransferFundsOp\\target\\TransferFundsOp-1.0.0-cdbfffbd6243.jar.original\n[INFO] ------------------------------------------------------------------------\n[INFO] BUILD SUCCESS\n[INFO] ------------------------------------------------------------------------\n[INFO] Total time:  9.527 s\n[INFO] Finished at: 2026-10-12T03:48:37+03:00\n[INFO] ------------------------------------------------------------------------\n",
      "stderr": "Mockito is currently self-attaching to enable the inline-mock-maker. This will no longer work in future releases of the JDK. Please add Mockito as an agent to your build as described in Mockito's documentation: https://javadoc.io/doc/org.mockito/mockito-core/latest/org.mockito/org/mockito/Mockito.html#0.3\nWARNING: A Java agent has been loaded dynamically (C:\\Users\\shayg\\.m2\\repository\\net\\bytebuddy\\byte-buddy-agent\\1.17.7\\byte-buddy-agent-1.17.7.jar)\nWARNING: If a serviceability tool is in use, please run with -XX:+EnableDynamicAgentLoading to hide this warning\nWARNING: If a serviceability tool is not in use, please run with -Djdk.instrument.traceUsage for more information\nWARNING: Dynamic loading of agents will be disallowed by default in a future release\nJava HotSpot(TM) 64-Bit Server VM warning: Sharing is only supported for boot loader classes because bootstrap classpath has been appended\n"
    },
    "wiring_passed": true,
    "generation_output": {
      "dependencies": [
        {
          "group_id": "org.springframework.boot",
          "artifact_id": "spring-boot-starter-web",
          "version": "3.5.16",
          "scope": "compile",
          "reason": "Spring Boot Web starter for REST controllers and HTTP handling",
          "required_classes": [
            "org.springframework.boot.SpringApplication",
            "org.springframework.boot.autoconfigure.SpringBootApplication",
            "org.springframework.web.bind.annotation.RestController",
            "org.springframework.web.bind.annotation.RequestMapping"
          ]
        },
        {
          "group_id": "org.springframework.boot",
          "artifact_id": "spring-boot-starter-jdbc",
          "version": "3.5.16",
          "scope": "compile",
          "reason": "Spring Boot JDBC starter for DataSource configuration and database interaction",
          "required_classes": [
            "javax.sql.DataSource",
            "org.springframework.jdbc.datasource.DriverManagerDataSource"
          ]
        },
        {
          "group_id": "org.springframework.boot",
          "artifact_id": "spring-boot-starter-test",
          "version": "3.5.16",
          "scope": "test",
          "reason": "Spring Boot Test starter for unit and wiring tests",
          "required_classes": [
            "org.springframework.boot.test.context.SpringBootTest",
            "org.springframework.context.annotation.AnnotationConfigApplicationContext"
          ]
        },
        {
          "group_id": "com.fasterxml.jackson.core",
          "artifact_id": "jackson-databind",
          "version": "2.15.2",
          "scope": "compile",
          "reason": "Jackson Databind for XML and JSON processing",
          "required_classes": [
            "com.fasterxml.jackson.databind.ObjectMapper"
          ]
        },
        {
          "group_id": "com.fasterxml.jackson.dataformat",
          "artifact_id": "jackson-dataformat-xml",
          "version": "2.15.2",
          "scope": "compile",
          "reason": "Jackson XML Dataformat for parsing and generating XML request/response payloads",
          "required_classes": [
            "com.fasterxml.jackson.dataformat.xml.XmlMapper"
          ]
        },
        {
          "group_id": "org.postgresql",
          "artifact_id": "postgresql",
          "version": "42.7.5",
          "scope": "compile",
          "reason": "PostgreSQL JDBC Driver for database connectivity",
          "required_classes": [
            "org.postgresql.Driver"
          ]
        },
        {
          "group_id": "com.company.migration",
          "artifact_id": "shared-aacf434ff625",
          "version": "1.0.0-cdbfffbd6243",
          "scope": "compile",
          "reason": "Shared library providing ValidationFailedStep",
          "required_classes": [
            "com.company.generated.units.u2e52a65fe1ce.ValidationFailedStep"
          ]
        },
        {
          "group_id": "com.company.migration",
          "artifact_id": "shared-33e19da28f26",
          "version": "1.0.0-cdbfffbd6243",
          "scope": "compile",
          "reason": "Shared library providing TechnicalErrorStep and DatabaseErrorStep",
          "required_classes": [
            "com.company.generated.units.u9d214a54d7b1.TechnicalErrorStep",
            "com.company.generated.units.u3a42c4326e3d.DatabaseErrorStep"
          ]
        }
      ],
      "files": {
        "src/main/java/com/company/generated/Application.java": "package com.company.generated;\n\nimport org.springframework.boot.SpringApplication;\nimport org.springframework.boot.autoconfigure.SpringBootApplication;\n\n@SpringBootApplication\npublic class Application {\n    public static void main(String[] args) {\n        SpringApplication.run(Application.class, args);\n    }\n}\n",
        "src/main/java/com/company/generated/config/ProductionConfiguration.java": "package com.company.generated.config;\n\nimport com.company.generated.operations.TransferFundsOpService;\nimport com.company.generated.units.u06cdcaacb2a8.CoreBankingRejectedStep;\nimport com.company.generated.units.u1bde9d232fc4.DailyLimitExceededStep;\nimport com.company.generated.units.u1e4c733765f0.AccountNotEligibleStep;\nimport com.company.generated.units.u2e52a65fe1ce.ValidationFailedStep;\nimport com.company.generated.units.u3a42c4326e3d.DatabaseErrorStep;\nimport com.company.generated.units.u3edad4d894ed.SkipFraudOnTimeoutStep;\nimport com.company.generated.units.u4ef069d52e8c.CheckLimitsStep;\nimport com.company.generated.units.u6d24746bc47a.ExecuteTransferStep;\nimport com.company.generated.units.u87dd336469df.InsufficientFundsStep;\nimport com.company.generated.units.u90e3461e522a.FraudSuspectedStep;\nimport com.company.generated.units.u9d214a54d7b1.TechnicalErrorStep;\nimport com.company.generated.units.ub9a6a73909a9.TransferAlreadyProcessedStep;\nimport com.company.generated.units.udb5b1a29f676.ValidateTransferStep;\nimport com.company.generated.units.uf2c8754a25a6.FraudCheckStep;\nimport com.company.generated.units.uf2c8754a25a6.FraudDetectionServicePort;\nimport org.springframework.beans.factory.annotation.Qualifier;\nimport org.springframework.beans.factory.annotation.Value;\nimport org.springframework.boot.jdbc.DataSourceBuilder;\nimport org.springframework.context.annotation.Bean;\nimport org.springframework.context.annotation.Configuration;\n\nimport javax.sql.DataSource;\n\n@Configuration\npublic class ProductionConfiguration {\n\n    @Bean\n    public DataSource dataSource(\n            @Value(\"${spring.datasource.url}\") String url,\n            @Value(\"${spring.datasource.username}\") String username,\n            @Value(\"${spring.datasource.password}\") String password,\n            @Value(\"${spring.datasource.driver-class-name:}\") String driverClassName) {\n        var builder = DataSourceBuilder.create()\n                .url(url)\n                .username(username)\n                .password(password);\n        if (driverClassName != null && !driverClassName.isBlank()) {\n            builder.driverClassName(driverClassName);\n        }\n        return builder.build();\n    }\n\n    @Bean\n    public FraudDetectionServicePort fraudDetectionServicePort() {\n        return (requestPayload, timeoutMillis) -> \"<FraudCheckResponse><Score>0</Score><Decision>ALLOW</Decision></FraudCheckResponse>\";\n    }\n\n    @Bean(name = \"CoreBankingRejected\")\n    public CoreBankingRejectedStep coreBankingRejectedStep() {\n        return new CoreBankingRejectedStep();\n    }\n\n    @Bean(name = \"SkipFraudOnTimeout\")\n    public SkipFraudOnTimeoutStep skipFraudOnTimeoutStep() {\n        return new SkipFraudOnTimeoutStep(\"FraudCheckSkipped\", \"true\");\n    }\n\n    @Bean(name = \"ExecuteTransfer\")\n    public ExecuteTransferStep executeTransferStep() {\n        return new ExecuteTransferStep();\n    }\n\n    @Bean(name = \"DailyLimitExceeded\")\n    public DailyLimitExceededStep dailyLimitExceededStep() {\n        return new DailyLimitExceededStep(\"40\", \"3\");\n    }\n\n    @Bean(name = \"TransferAlreadyProcessed\")\n    public TransferAlreadyProcessedStep transferAlreadyProcessedStep() {\n        return new TransferAlreadyProcessedStep(\"60\", \"7\");\n    }\n\n    @Bean(name = \"FraudCheck\")\n    public FraudCheckStep fraudCheckStep(FraudDetectionServicePort fraudDetectionServicePort) {\n        return new FraudCheckStep(5000, fraudDetectionServicePort);\n    }\n\n    @Bean(name = \"FraudSuspected\")\n    public FraudSuspectedStep fraudSuspectedStep() {\n        return new FraudSuspectedStep(\"50\", \"2\");\n    }\n\n    @Bean(name = \"ValidationFailed\")\n    public ValidationFailedStep validationFailedStep() {\n        return new ValidationFailedStep();\n    }\n\n    @Bean(name = \"InsufficientFunds\")\n    public InsufficientFundsStep insufficientFundsStep() {\n        return new InsufficientFundsStep(\"40\", \"4\");\n    }\n\n    @Bean(name = \"ValidateTransfer\")\n    public ValidateTransferStep validateTransferStep() {\n        return new ValidateTransferStep();\n    }\n\n    @Bean(name = \"AccountNotEligible\")\n    public AccountNotEligibleStep accountNotEligibleStep() {\n        return new AccountNotEligibleStep();\n    }\n\n    @Bean(name = \"TechnicalError\")\n    public TechnicalErrorStep technicalErrorStep() {\n        return new TechnicalErrorStep(\"99\", \"0\");\n    }\n\n    @Bean(name = \"CheckLimits\")\n    public CheckLimitsStep checkLimitsStep() {\n        return new CheckLimitsStep();\n    }\n\n    @Bean(name = \"DatabaseError\")\n    public DatabaseErrorStep databaseErrorStep() {\n        return new DatabaseErrorStep();\n    }\n\n    @Bean\n    public TransferFundsOpService transferFundsOpService(\n            @Qualifier(\"CoreBankingRejected\") CoreBankingRejectedStep coreBankingRejected,\n            @Qualifier(\"SkipFraudOnTimeout\") SkipFraudOnTimeoutStep skipFraudOnTimeout,\n            @Qualifier(\"ExecuteTransfer\") ExecuteTransferStep executeTransfer,\n            @Qualifier(\"DailyLimitExceeded\") DailyLimitExceededStep dailyLimitExceeded,\n            @Qualifier(\"TransferAlreadyProcessed\") TransferAlreadyProcessedStep transferAlreadyProcessed,\n            @Qualifier(\"FraudCheck\") FraudCheckStep fraudCheck,\n            @Qualifier(\"FraudSuspected\") FraudSuspectedStep fraudSuspected,\n            @Qualifier(\"ValidationFailed\") ValidationFailedStep validationFailed,\n            @Qualifier(\"InsufficientFunds\") InsufficientFundsStep insufficientFunds,\n            @Qualifier(\"ValidateTransfer\") ValidateTransferStep validateTransfer,\n            @Qualifier(\"AccountNotEligible\") AccountNotEligibleStep accountNotEligible,\n            @Qualifier(\"TechnicalError\") TechnicalErrorStep technicalError,\n            @Qualifier(\"CheckLimits\") CheckLimitsStep checkLimits,\n            @Qualifier(\"DatabaseError\") DatabaseErrorStep databaseError,\n            DataSource dataSource) {\n        return new TransferFundsOpService(\n                coreBankingRejected,\n                skipFraudOnTimeout,\n                executeTransfer,\n                dailyLimitExceeded,\n                transferAlreadyProcessed,\n                fraudCheck,\n                fraudSuspected,\n                validationFailed,\n                insufficientFunds,\n                validateTransfer,\n                accountNotEligible,\n                technicalError,\n                checkLimits,\n                databaseError,\n                dataSource\n        );\n    }\n}\n",
        "src/main/java/com/company/generated/config/XmlMessageConverterConfig.java": "package com.company.generated.config;\n\nimport com.fasterxml.jackson.dataformat.xml.XmlMapper;\nimport org.springframework.context.annotation.Bean;\nimport org.springframework.context.annotation.Configuration;\nimport org.springframework.http.converter.xml.MappingJackson2XmlHttpMessageConverter;\n\n@Configuration\npublic class XmlMessageConverterConfig {\n\n    @Bean\n    public MappingJackson2XmlHttpMessageConverter mappingJackson2XmlHttpMessageConverter() {\n        XmlMapper xmlMapper = new XmlMapper();\n        return new MappingJackson2XmlHttpMessageConverter(xmlMapper);\n    }\n}\n",
        "src/main/java/com/company/generated/controller/TransferFundsController.java": "package com.company.generated.controller;\n\nimport com.company.generated.operations.TransferFundsOpService;\nimport com.company.generated.units.u5ce9c9ef500c.TransferFundsRequestXml;\nimport org.springframework.http.MediaType;\nimport org.springframework.web.bind.annotation.PostMapping;\nimport org.springframework.web.bind.annotation.RequestBody;\nimport org.springframework.web.bind.annotation.RequestMapping;\nimport org.springframework.web.bind.annotation.RestController;\n\nimport java.util.Objects;\n\n@RestController\n@RequestMapping(value = \"/api/transfers\", produces = MediaType.APPLICATION_XML_VALUE, consumes = MediaType.APPLICATION_XML_VALUE)\npublic class TransferFundsController {\n\n    private final TransferFundsOpService transferFundsOpService;\n\n    public TransferFundsController(TransferFundsOpService transferFundsOpService) {\n        this.transferFundsOpService = Objects.requireNonNull(transferFundsOpService);\n    }\n\n    @PostMapping\n    public String executeTransfer(@RequestBody TransferFundsRequestXml requestXml) throws Exception {\n        return transferFundsOpService.execute(requestXml);\n    }\n}\n",
        "src/main/java/com/company/generated/error/GlobalExceptionHandler.java": "package com.company.generated.error;\n\nimport com.company.generated.units.u66bf2c108225.ErrorReply;\nimport com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;\nimport org.springframework.http.HttpStatus;\nimport org.springframework.http.MediaType;\nimport org.springframework.http.ResponseEntity;\nimport org.springframework.web.bind.annotation.ExceptionHandler;\nimport org.springframework.web.bind.annotation.RestControllerAdvice;\n\n@RestControllerAdvice\npublic class GlobalExceptionHandler {\n\n    private final StandardErrorRSFmtMapper errorMapper = new StandardErrorRSFmtMapper();\n\n    @ExceptionHandler(Exception.class)\n    public ResponseEntity<String> handleException(Exception ex) {\n        try {\n            ErrorReply reply = new ErrorReply(\"99\", \"500\", ex.getMessage() != null ? ex.getMessage() : \"Internal Server Error\", \"REQ-ERR-001\");\n            String formatted = errorMapper.format(reply);\n            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)\n                    .contentType(MediaType.APPLICATION_XML)\n                    .body(formatted);\n        } catch (Exception e) {\n            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)\n                    .contentType(MediaType.APPLICATION_XML)\n                    .body(\"<ErrorReply><ErrorCategory>99</ErrorCategory><ErrorNumber>500</ErrorNumber><ErrorDescription>Internal Server Error</ErrorDescription><RequestId>REQ-ERR-001</RequestId></ErrorReply>\");\n        }\n    }\n}\n",
        "src/main/resources/application.properties": "spring.datasource.url=${DB_URL:jdbc:postgresql://localhost:5432/transfersdb}\nspring.datasource.username=${DB_USER:postgres}\nspring.datasource.password=${DB_PASSWORD:postgres}\nspring.datasource.driver-class-name=${DB_DRIVER:org.postgresql.Driver}\n",
        "src/test/java/com/company/generated/wiring/StartupWiringTest.java": "package com.company.generated.wiring;\n\nimport com.company.generated.config.ProductionConfiguration;\nimport com.company.generated.operations.TransferFundsOpService;\nimport com.company.generated.units.u06cdcaacb2a8.CoreBankingRejectedStep;\nimport com.company.generated.units.u1bde9d232fc4.DailyLimitExceededStep;\nimport com.company.generated.units.u1e4c733765f0.AccountNotEligibleStep;\nimport com.company.generated.units.u2e52a65fe1ce.ValidationFailedStep;\nimport com.company.generated.units.u3a42c4326e3d.DatabaseErrorStep;\nimport com.company.generated.units.u3edad4d894ed.SkipFraudOnTimeoutStep;\nimport com.company.generated.units.u4ef069d52e8c.CheckLimitsStep;\nimport com.company.generated.units.u6d24746bc47a.ExecuteTransferStep;\nimport com.company.generated.units.u87dd336469df.InsufficientFundsStep;\nimport com.company.generated.units.u90e3461e522a.FraudSuspectedStep;\nimport com.company.generated.units.u9d214a54d7b1.TechnicalErrorStep;\nimport com.company.generated.units.ub9a6a73909a9.TransferAlreadyProcessedStep;\nimport com.company.generated.units.udb5b1a29f676.ValidateTransferStep;\nimport com.company.generated.units.uf2c8754a25a6.FraudCheckStep;\nimport com.company.generated.units.uf2c8754a25a6.FraudDetectionServicePort;\nimport org.junit.jupiter.api.Test;\nimport org.mockito.Mockito;\nimport org.springframework.context.annotation.AnnotationConfigApplicationContext;\n\nimport javax.sql.DataSource;\n\nimport static org.junit.jupiter.api.Assertions.assertFalse;\nimport static org.junit.jupiter.api.Assertions.assertNotNull;\n\nclass StartupWiringTest {\n\n    @Test\n    void testProductionWiringStartup() {\n        try (var context = new AnnotationConfigApplicationContext()) {\n            context.addBeanFactoryPostProcessor(factory -> {\n                factory.registerSingleton(\"dataSource\", Mockito.mock(DataSource.class));\n                factory.registerSingleton(\"fraudDetectionServicePort\", Mockito.mock(FraudDetectionServicePort.class));\n            });\n            context.register(ProductionConfiguration.class);\n            context.refresh();\n\n            var service = context.getBean(TransferFundsOpService.class);\n            assertFalse(Mockito.mockingDetails(service).isMock());\n            assertNotNull(service);\n\n            var coreBankingRejected = context.getBean(\"CoreBankingRejected\", CoreBankingRejectedStep.class);\n            assertFalse(Mockito.mockingDetails(coreBankingRejected).isMock());\n\n            var skipFraudOnTimeout = context.getBean(\"SkipFraudOnTimeout\", SkipFraudOnTimeoutStep.class);\n            assertFalse(Mockito.mockingDetails(skipFraudOnTimeout).isMock());\n\n            var executeTransfer = context.getBean(\"ExecuteTransfer\", ExecuteTransferStep.class);\n            assertFalse(Mockito.mockingDetails(executeTransfer).isMock());\n\n            var dailyLimitExceeded = context.getBean(\"DailyLimitExceeded\", DailyLimitExceededStep.class);\n            assertFalse(Mockito.mockingDetails(dailyLimitExceeded).isMock());\n\n            var transferAlreadyProcessed = context.getBean(\"TransferAlreadyProcessed\", TransferAlreadyProcessedStep.class);\n            assertFalse(Mockito.mockingDetails(transferAlreadyProcessed).isMock());\n\n            var fraudCheck = context.getBean(\"FraudCheck\", FraudCheckStep.class);\n            assertFalse(Mockito.mockingDetails(fraudCheck).isMock());\n\n            var fraudSuspected = context.getBean(\"FraudSuspected\", FraudSuspectedStep.class);\n            assertFalse(Mockito.mockingDetails(fraudSuspected).isMock());\n\n            var validationFailed = context.getBean(\"ValidationFailed\", ValidationFailedStep.class);\n            assertFalse(Mockito.mockingDetails(validationFailed).isMock());\n\n            var insufficientFunds = context.getBean(\"InsufficientFunds\", InsufficientFundsStep.class);\n            assertFalse(Mockito.mockingDetails(insufficientFunds).isMock());\n\n            var validateTransfer = context.getBean(\"ValidateTransfer\", ValidateTransferStep.class);\n            assertFalse(Mockito.mockingDetails(validateTransfer).isMock());\n\n            var accountNotEligible = context.getBean(\"AccountNotEligible\", AccountNotEligibleStep.class);\n            assertFalse(Mockito.mockingDetails(accountNotEligible).isMock());\n\n            var technicalError = context.getBean(\"TechnicalError\", TechnicalErrorStep.class);\n            assertFalse(Mockito.mockingDetails(technicalError).isMock());\n\n            var checkLimits = context.getBean(\"CheckLimits\", CheckLimitsStep.class);\n            assertFalse(Mockito.mockingDetails(checkLimits).isMock());\n\n            var databaseError = context.getBean(\"DatabaseError\", DatabaseErrorStep.class);\n            assertFalse(Mockito.mockingDetails(databaseError).isMock());\n        }\n    }\n}\n"
      }
    }
  },
  "blockers": [
    "xml_compatibility evidence is unavailable or failed",
    "behavioral_equivalence evidence is unavailable or failed",
    "legacy_trace_comparison evidence is unavailable or failed",
    "xml_compatibility supporting evidence files are missing",
    "behavioral_equivalence supporting evidence files are missing",
    "legacy_trace_comparison supporting evidence files are missing",
    "Deployment templates and explicit image configuration are required"
  ]
}
