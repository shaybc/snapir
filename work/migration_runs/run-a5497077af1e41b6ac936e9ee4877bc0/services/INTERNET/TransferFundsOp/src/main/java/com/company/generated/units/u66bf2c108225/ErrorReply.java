package com.company.generated.units.u66bf2c108225;

public class ErrorReply {
    private String errorCategory;
    private String errorNumber;
    private String errorDescription;
    private String requestId;

    public ErrorReply() {}

    public ErrorReply(String errorCategory, String errorNumber, String errorDescription, String requestId) {
        this.errorCategory = errorCategory;
        this.errorNumber = errorNumber;
        this.errorDescription = errorDescription;
        this.requestId = requestId;
    }

    public String getErrorCategory() {
        return errorCategory;
    }

    public void setErrorCategory(String errorCategory) {
        this.errorCategory = errorCategory;
    }

    public String getErrorNumber() {
        return errorNumber;
    }

    public void setErrorNumber(String errorNumber) {
        this.errorNumber = errorNumber;
    }

    public String getErrorDescription() {
        return errorDescription;
    }

    public void setErrorDescription(String errorDescription) {
        this.errorDescription = errorDescription;
    }

    public String getRequestId() {
        return requestId;
    }

    public void setRequestId(String requestId) {
        this.requestId = requestId;
    }
}
