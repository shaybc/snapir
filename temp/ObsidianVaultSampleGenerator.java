import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

public class ObsidianVaultSampleGenerator {

    public static void main(String[] args) {
        if (args.length != 1) {
            System.err.println("Usage: java ObsidianVaultSampleGenerator <obsidian-vault-root-folder>");
            System.exit(1);
        }

        Path vaultRoot = Path.of(args[0]);

        try {
            createSampleVaultStructure(vaultRoot);
            System.out.println("Obsidian sample files created successfully under: " + vaultRoot.toAbsolutePath());
        } catch (IOException e) {
            System.err.println("Failed to create Obsidian sample files: " + e.getMessage());
            e.printStackTrace();
            System.exit(2);
        }
    }

    private static void createSampleVaultStructure(Path vaultRoot) throws IOException {
        Map<String, String> files = new LinkedHashMap<>();

        files.put("operations/GetClientLinksOp.md", """
                ---
                entity_type: operation
                entity_id: GetClientLinksOp
                source_file: operations/GetClientLinks.xml
                ---

                # GetClientLinksOp

                ## Summary
                Retrieves client links from backend, maps results into response format, and handles error scenarios.

                ## Context
                - [[GetClientLinksContext]]

                ## Steps
                - [[Step_GetClientLinks]]
                - [[Step_ErrorDataNotFound]]
                - [[Step_ErrorInvalidLinks]]
                - [[Step_OperationFailed]]

                ## Formats
                - Request: [[Fmt_GetClientLinks_Request]]
                - Response: [[Fmt_GetClientLinks_Response]]

                ## Flow
                ```mermaid
                graph TD
                  A[Step_GetClientLinks] -->|0| END
                  A -->|4| B[Step_ErrorDataNotFound]
                  A -->|5| C[Step_ErrorInvalidLinks]
                  A -->|other| D[Step_OperationFailed]
                ```

                ## Java Dependencies
                - [[Class_db.GetClientLinksSP]]
                - [[Class_operations.MapErrorByValueAlways]]

                ## External Dependencies (Inferred)
                - Database
                - Possibly internal service layer

                ## Microservice Signals
                - Domain: Client Links
                - Strong DB coupling
                - Reusable error handlers
                - Candidate: Extract as "Links Service"
                """);

        files.put("opsteps/Step_GetClientLinks.md", """
                ---
                entity_type: opStep
                entity_id: Step_GetClientLinks
                ---

                # Step_GetClientLinks

                ## Parent Operation
                - [[GetClientLinksOp]]

                ## Implementation
                - [[Class_db.GetClientLinksSP]]

                ## Inputs
                - Reads from [[GetClientLinksContext]]

                ## Outputs
                - Writes results into [[GetClientLinksContext]]

                ## Transitions
                - `0` → END
                - `4` → [[Step_ErrorDataNotFound]]
                - `5` → [[Step_ErrorInvalidLinks]]
                - `other` → [[Step_OperationFailed]]

                ## Inferred Behavior
                Executes a stored procedure to retrieve client link data.
                """);

        files.put("opsteps/Step_ErrorDataNotFound.md", """
                ---
                entity_type: opStep
                entity_id: Step_ErrorDataNotFound
                ---

                # Step_ErrorDataNotFound

                ## Parent Operation
                - [[GetClientLinksOp]]

                ## Implementation
                - [[Class_operations.MapErrorByValueAlways]]

                ## Inputs
                - Reads from [[GetClientLinksContext]]

                ## Outputs
                - Writes error details into [[GetClientLinksContext]]

                ## Behavior
                Maps "data not found" error into response structure.
                """);

        files.put("opsteps/Step_ErrorInvalidLinks.md", """
                ---
                entity_type: opStep
                entity_id: Step_ErrorInvalidLinks
                ---

                # Step_ErrorInvalidLinks

                ## Parent Operation
                - [[GetClientLinksOp]]

                ## Implementation
                - [[Class_operations.MapErrorByValueAlways]]

                ## Inputs
                - Reads from [[GetClientLinksContext]]

                ## Outputs
                - Writes error details into [[GetClientLinksContext]]

                ## Behavior
                Maps invalid links error into response structure.
                """);

        files.put("opsteps/Step_OperationFailed.md", """
                ---
                entity_type: opStep
                entity_id: Step_OperationFailed
                ---

                # Step_OperationFailed

                ## Parent Operation
                - [[GetClientLinksOp]]

                ## Inputs
                - Reads from [[GetClientLinksContext]]

                ## Outputs
                - Writes generic failure result into [[GetClientLinksContext]]

                ## Behavior
                Fallback error handler for unexpected return codes.
                """);

        files.put("formats/Fmt_GetClientLinks_Request.md", """
                ---
                entity_type: format
                entity_id: Fmt_GetClientLinks_Request
                ---

                # Fmt_GetClientLinks_Request

                ## Structure
                ```xml
                <GetLinks>
                  <ClientId/>
                  <ClientName/>
                </GetLinks>
                ```

                ## Used By
                - [[GetClientLinksOp]]

                ## Purpose
                Defines the input XML schema for the operation.
                """);

        files.put("formats/Fmt_GetClientLinks_Response.md", """
                ---
                entity_type: format
                entity_id: Fmt_GetClientLinks_Response
                ---

                # Fmt_GetClientLinks_Response

                ## Structure
                ```xml
                <Response>
                  <GetLinks>
                    <ReqParams>
                      <ClientId/>
                      <ClientName/>
                    </ReqParams>
                    <LinksBlock>
                      <DocData>
                        <DocId/>
                        <Flag/>
                        <LinkDescription/>
                        <StoreDate/>
                        <MaxAccess/>
                        <WrittenAt/>
                      </DocData>
                    </LinksBlock>
                  </GetLinks>
                </Response>
                ```

                ## Used By
                - [[GetClientLinksOp]]

                ## Notes
                - Contains collection-like response content under `LinksBlock`
                - Includes DB-derived field `LinkDescription`
                """);

        files.put("contexts/GetClientLinksContext.md", """
                ---
                entity_type: context
                entity_id: GetClientLinksContext
                ---

                # GetClientLinksContext

                ## Purpose
                Shared data container across the operation lifecycle.

                ## Used By
                - [[GetClientLinksOp]]
                - [[Step_GetClientLinks]]
                - [[Step_ErrorDataNotFound]]
                - [[Step_ErrorInvalidLinks]]
                - [[Step_OperationFailed]]

                ## Data Flow
                - Input XML parsed into context
                - Steps read and write values
                - Response generated from context
                """);

        files.put("classes/Class_db.GetClientLinksSP.md", """
                ---
                entity_type: java_class
                entity_id: Class_db.GetClientLinksSP
                ---

                # Class_db.GetClientLinksSP

                ## Package
                db

                ## Type
                Stored Procedure Executor

                ## Responsibilities
                - Fetch client links from database
                - Populate [[GetClientLinksContext]] with results

                ## Likely Calls
                - JDBC
                - Stored Procedure

                ## Used By
                - [[Step_GetClientLinks]]
                """);

        files.put("classes/Class_operations.MapErrorByValueAlways.md", """
                ---
                entity_type: java_class
                entity_id: Class_operations.MapErrorByValueAlways
                ---

                # Class_operations.MapErrorByValueAlways

                ## Package
                operations

                ## Type
                Error Mapper

                ## Responsibilities
                - Map error codes into response fields
                - Populate error category and number in [[GetClientLinksContext]]

                ## Used By
                - [[Step_ErrorDataNotFound]]
                - [[Step_ErrorInvalidLinks]]
                """);

        files.put("analysis/GlobalRelationshipsOverview.md", """
                ---
                entity_type: analysis
                entity_id: GlobalRelationshipsOverview
                ---

                # GlobalRelationshipsOverview

                ## Operations → Steps
                - [[GetClientLinksOp]] → [[Step_GetClientLinks]]
                - [[GetClientLinksOp]] → [[Step_ErrorDataNotFound]]
                - [[GetClientLinksOp]] → [[Step_ErrorInvalidLinks]]
                - [[GetClientLinksOp]] → [[Step_OperationFailed]]

                ## Steps → Classes
                - [[Step_GetClientLinks]] → [[Class_db.GetClientLinksSP]]
                - [[Step_ErrorDataNotFound]] → [[Class_operations.MapErrorByValueAlways]]
                - [[Step_ErrorInvalidLinks]] → [[Class_operations.MapErrorByValueAlways]]

                ## Operation → Formats
                - [[GetClientLinksOp]] → [[Fmt_GetClientLinks_Request]]
                - [[GetClientLinksOp]] → [[Fmt_GetClientLinks_Response]]

                ## Operation → Context
                - [[GetClientLinksOp]] → [[GetClientLinksContext]]

                ## Notes for AI Agents
                Questions that should work well:
                - What does [[GetClientLinksOp]] do?
                - Which Java class executes [[Step_GetClientLinks]]?
                - Which format defines the response?
                - What happens if return code = 4?
                """);

        for (Map.Entry<String, String> entry : files.entrySet()) {
            Path filePath = vaultRoot.resolve(entry.getKey());
            Files.createDirectories(filePath.getParent());
            Files.writeString(filePath, entry.getValue(), StandardCharsets.UTF_8);
        }
    }
}