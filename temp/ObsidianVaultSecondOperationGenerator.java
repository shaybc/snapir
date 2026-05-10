import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Adds a second sample operation into an existing Obsidian vault.
 *
 * Shared resources from the first operation:
 * 1. [[GetClientLinksContext]]
 * 2. [[Class_operations.MapErrorByValueAlways]]
 * 3. [[Step_OperationFailed]]
 *
 * New resources are also created for the second operation.
 */
public class ObsidianVaultSecondOperationGenerator {

    public static void main(String[] args) {
        if (args.length != 1) {
            System.err.println("Usage: java ObsidianVaultSecondOperationGenerator <obsidian-vault-root-folder>");
            System.exit(1);
        }

        Path vaultRoot = Path.of(args[0]);

        try {
            createSecondOperation(vaultRoot);
            System.out.println("Second operation files created successfully under: " + vaultRoot.toAbsolutePath());
        } catch (IOException e) {
            System.err.println("Failed to create second operation files: " + e.getMessage());
            e.printStackTrace();
            System.exit(2);
        }
    }

    private static void createSecondOperation(Path vaultRoot) throws IOException {
        writeFile(
                vaultRoot.resolve("operations/GetClientProfileOp.md"),
                """
                ---
                entity_type: operation
                entity_id: GetClientProfileOp
                source_file: operations/GetClientProfile.xml
                ---

                # GetClientProfileOp

                ## Summary
                Retrieves a client profile, validates eligibility, enriches profile data, and maps the response.

                ## Shared Resources From First Operation
                - [[GetClientLinksContext]]
                - [[Class_operations.MapErrorByValueAlways]]
                - [[Step_OperationFailed]]

                ## Context
                - [[GetClientLinksContext]]

                ## Steps
                - [[Step_LoadClientProfile]]
                - [[Step_ValidateClientStatus]]
                - [[Step_EnrichClientProfile]]
                - [[Step_ErrorProfileNotFound]]
                - [[Step_ErrorClientBlocked]]
                - [[Step_OperationFailed]]

                ## Formats
                - Request: [[Fmt_GetClientProfile_Request]]
                - Response: [[Fmt_GetClientProfile_Response]]

                ## Flow
                ```mermaid
                graph TD
                  A[Step_LoadClientProfile] -->|0| B[Step_ValidateClientStatus]
                  A -->|4| D[Step_ErrorProfileNotFound]
                  A -->|other| F[Step_OperationFailed]

                  B -->|0| C[Step_EnrichClientProfile]
                  B -->|7| E[Step_ErrorClientBlocked]
                  B -->|other| F

                  C -->|0| END
                  C -->|other| F

                  D -->|other| F
                  E -->|other| F
                ```

                ## Java Dependencies
                - [[Class_db.GetClientProfileSP]]
                - [[Class_operations.ValidateClientStatus]]
                - [[Class_services.EnrichClientProfile]]
                - [[Class_operations.MapErrorByValueAlways]]

                ## External Dependencies (Inferred)
                - Database
                - Internal validation service
                - Profile enrichment service

                ## Microservice Signals
                - Domain: Client Profile
                - Shared context with links operation
                - Reuses common error handling
                - Candidate: Extract as "Client Profile Service"
                """
        );

        writeFile(
                vaultRoot.resolve("opsteps/Step_LoadClientProfile.md"),
                """
                ---
                entity_type: opStep
                entity_id: Step_LoadClientProfile
                ---

                # Step_LoadClientProfile

                ## Parent Operation
                - [[GetClientProfileOp]]

                ## Implementation
                - [[Class_db.GetClientProfileSP]]

                ## Inputs
                - Reads from [[GetClientLinksContext]]

                ## Outputs
                - Writes profile base data into [[GetClientLinksContext]]

                ## Transitions
                - `0` → [[Step_ValidateClientStatus]]
                - `4` → [[Step_ErrorProfileNotFound]]
                - `other` → [[Step_OperationFailed]]

                ## Inferred Behavior
                Loads the main client profile from the database.
                """
        );

        writeFile(
                vaultRoot.resolve("opsteps/Step_ValidateClientStatus.md"),
                """
                ---
                entity_type: opStep
                entity_id: Step_ValidateClientStatus
                ---

                # Step_ValidateClientStatus

                ## Parent Operation
                - [[GetClientProfileOp]]

                ## Implementation
                - [[Class_operations.ValidateClientStatus]]

                ## Inputs
                - Reads loaded profile from [[GetClientLinksContext]]

                ## Outputs
                - Writes validation result into [[GetClientLinksContext]]

                ## Transitions
                - `0` → [[Step_EnrichClientProfile]]
                - `7` → [[Step_ErrorClientBlocked]]
                - `other` → [[Step_OperationFailed]]

                ## Inferred Behavior
                Checks whether the client is active and allowed to continue.
                """
        );

        writeFile(
                vaultRoot.resolve("opsteps/Step_EnrichClientProfile.md"),
                """
                ---
                entity_type: opStep
                entity_id: Step_EnrichClientProfile
                ---

                # Step_EnrichClientProfile

                ## Parent Operation
                - [[GetClientProfileOp]]

                ## Implementation
                - [[Class_services.EnrichClientProfile]]

                ## Inputs
                - Reads current profile data from [[GetClientLinksContext]]

                ## Outputs
                - Writes enriched profile data into [[GetClientLinksContext]]

                ## Transitions
                - `0` → END
                - `other` → [[Step_OperationFailed]]

                ## Inferred Behavior
                Enriches the client profile with additional derived or external data.
                """
        );

        writeFile(
                vaultRoot.resolve("opsteps/Step_ErrorProfileNotFound.md"),
                """
                ---
                entity_type: opStep
                entity_id: Step_ErrorProfileNotFound
                ---

                # Step_ErrorProfileNotFound

                ## Parent Operation
                - [[GetClientProfileOp]]

                ## Implementation
                - [[Class_operations.MapErrorByValueAlways]]

                ## Shared Resource
                - [[Class_operations.MapErrorByValueAlways]]

                ## Inputs
                - Reads from [[GetClientLinksContext]]

                ## Outputs
                - Writes error details into [[GetClientLinksContext]]

                ## Behavior
                Maps "profile not found" error into the response structure.
                """
        );

        writeFile(
                vaultRoot.resolve("opsteps/Step_ErrorClientBlocked.md"),
                """
                ---
                entity_type: opStep
                entity_id: Step_ErrorClientBlocked
                ---

                # Step_ErrorClientBlocked

                ## Parent Operation
                - [[GetClientProfileOp]]

                ## Implementation
                - [[Class_operations.MapErrorByValueAlways]]

                ## Shared Resource
                - [[Class_operations.MapErrorByValueAlways]]

                ## Inputs
                - Reads from [[GetClientLinksContext]]

                ## Outputs
                - Writes blocked-client error details into [[GetClientLinksContext]]

                ## Behavior
                Maps "client blocked" error into the response structure.
                """
        );

        writeFile(
                vaultRoot.resolve("formats/Fmt_GetClientProfile_Request.md"),
                """
                ---
                entity_type: format
                entity_id: Fmt_GetClientProfile_Request
                ---

                # Fmt_GetClientProfile_Request

                ## Structure
                ```xml
                <GetClientProfile>
                  <ClientId/>
                  <ChannelCode/>
                  <RequestId/>
                </GetClientProfile>
                ```

                ## Used By
                - [[GetClientProfileOp]]

                ## Purpose
                Defines the input XML schema for the client profile operation.
                """
        );

        writeFile(
                vaultRoot.resolve("formats/Fmt_GetClientProfile_Response.md"),
                """
                ---
                entity_type: format
                entity_id: Fmt_GetClientProfile_Response
                ---

                # Fmt_GetClientProfile_Response

                ## Structure
                ```xml
                <Response>
                  <ClientProfile>
                    <ClientId/>
                    <FullName/>
                    <Status/>
                    <Segment/>
                    <RiskLevel/>
                    <PreferredLanguage/>
                    <Contacts>
                      <Phone/>
                      <Email/>
                    </Contacts>
                    <Addresses>
                      <Address>
                        <City/>
                        <Street/>
                        <ZipCode/>
                      </Address>
                    </Addresses>
                  </ClientProfile>
                </Response>
                ```

                ## Used By
                - [[GetClientProfileOp]]

                ## Notes
                - Contains nested profile data
                - Contains nested contacts and addresses sections
                """
        );

        writeFile(
                vaultRoot.resolve("classes/Class_db.GetClientProfileSP.md"),
                """
                ---
                entity_type: java_class
                entity_id: Class_db.GetClientProfileSP
                ---

                # Class_db.GetClientProfileSP

                ## Package
                db

                ## Type
                Stored Procedure Executor

                ## Responsibilities
                - Fetch client profile from database
                - Populate [[GetClientLinksContext]] with profile data

                ## Likely Calls
                - JDBC
                - Stored Procedure

                ## Used By
                - [[Step_LoadClientProfile]]
                """
        );

        writeFile(
                vaultRoot.resolve("classes/Class_operations.ValidateClientStatus.md"),
                """
                ---
                entity_type: java_class
                entity_id: Class_operations.ValidateClientStatus
                ---

                # Class_operations.ValidateClientStatus

                ## Package
                operations

                ## Type
                Validation Step

                ## Responsibilities
                - Validate client status
                - Detect blocked or inactive clients
                - Update [[GetClientLinksContext]] with validation outcome

                ## Used By
                - [[Step_ValidateClientStatus]]
                """
        );

        writeFile(
                vaultRoot.resolve("classes/Class_services.EnrichClientProfile.md"),
                """
                ---
                entity_type: java_class
                entity_id: Class_services.EnrichClientProfile
                ---

                # Class_services.EnrichClientProfile

                ## Package
                services

                ## Type
                Enrichment Service

                ## Responsibilities
                - Add derived and supplemental profile information
                - Update [[GetClientLinksContext]] with enriched values

                ## Likely Calls
                - Internal service API
                - Helper services

                ## Used By
                - [[Step_EnrichClientProfile]]
                """
        );

        writeFile(
                vaultRoot.resolve("analysis/SecondOperationOverview.md"),
                """
                ---
                entity_type: analysis
                entity_id: SecondOperationOverview
                ---

                # SecondOperationOverview

                ## Shared Resources With First Operation
                - [[GetClientLinksContext]]
                - [[Class_operations.MapErrorByValueAlways]]
                - [[Step_OperationFailed]]

                ## New Operation
                - [[GetClientProfileOp]]

                ## New Steps
                - [[Step_LoadClientProfile]]
                - [[Step_ValidateClientStatus]]
                - [[Step_EnrichClientProfile]]
                - [[Step_ErrorProfileNotFound]]
                - [[Step_ErrorClientBlocked]]

                ## New Formats
                - [[Fmt_GetClientProfile_Request]]
                - [[Fmt_GetClientProfile_Response]]

                ## New Classes
                - [[Class_db.GetClientProfileSP]]
                - [[Class_operations.ValidateClientStatus]]
                - [[Class_services.EnrichClientProfile]]

                ## Relationship Summary
                - [[GetClientProfileOp]] shares the same context as [[GetClientLinksOp]]
                - [[GetClientProfileOp]] reuses [[Class_operations.MapErrorByValueAlways]]
                - [[GetClientProfileOp]] reuses [[Step_OperationFailed]]
                - [[GetClientProfileOp]] introduces more steps and more classes than the first operation
                """
        );
    }

    private static void writeFile(Path filePath, String content) throws IOException {
        Files.createDirectories(filePath.getParent());
        Files.writeString(filePath, content, StandardCharsets.UTF_8);
    }
}