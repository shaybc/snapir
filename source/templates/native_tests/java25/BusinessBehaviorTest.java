package example;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;

/** Reference structure only: derive real expected values from migration evidence. */
public class BusinessBehaviorTest {
    interface NotificationPort { void send(String reference); }
    static class CompletionService {
        private final NotificationPort notifications;
        CompletionService(NotificationPort notifications) { this.notifications = notifications; }
        String complete(String reference) { notifications.send(reference); return reference; }
    }

    @Test void returnsTheCompletedReference() {
        NotificationPort notifications = mock(NotificationPort.class);
        CompletionService service = new CompletionService(notifications);
        assertEquals("sample-reference", service.complete("sample-reference"));
    }

    @Test void notifiesTheCollaboratorOnce() {
        NotificationPort notifications = mock(NotificationPort.class);
        new CompletionService(notifications).complete("sample-reference");
        verify(notifications).send("sample-reference");
        verifyNoMoreInteractions(notifications);
    }
}
