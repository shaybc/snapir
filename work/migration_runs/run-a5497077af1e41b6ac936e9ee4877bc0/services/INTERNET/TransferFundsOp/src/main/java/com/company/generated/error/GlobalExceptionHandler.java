package com.company.generated.error;

import com.company.generated.units.u66bf2c108225.ErrorReply;
import com.company.generated.units.u66bf2c108225.StandardErrorRSFmtMapper;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {

    private final StandardErrorRSFmtMapper errorMapper = new StandardErrorRSFmtMapper();

    @ExceptionHandler(Exception.class)
    public ResponseEntity<String> handleException(Exception ex) {
        try {
            ErrorReply reply = new ErrorReply("99", "500", ex.getMessage() != null ? ex.getMessage() : "Internal Server Error", "REQ-ERR-001");
            String formatted = errorMapper.format(reply);
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_XML)
                    .body(formatted);
        } catch (Exception e) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .contentType(MediaType.APPLICATION_XML)
                    .body("<ErrorReply><ErrorCategory>99</ErrorCategory><ErrorNumber>500</ErrorNumber><ErrorDescription>Internal Server Error</ErrorDescription><RequestId>REQ-ERR-001</RequestId></ErrorReply>");
        }
    }
}
