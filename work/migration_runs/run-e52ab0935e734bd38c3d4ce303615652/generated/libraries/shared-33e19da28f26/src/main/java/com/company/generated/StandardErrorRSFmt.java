package com.company.generated;

import jakarta.xml.bind.annotation.XmlElement;
import jakarta.xml.bind.annotation.XmlRootElement;

@XmlRootElement(name = "ErrorReply")
public class StandardErrorRSFmt {

    private String errorCategory;
    private String errorNumber;
    private String errorDescription;
    private String requestId;

    public StandardErrorRSFmt() {
    }

    @XmlElement(name = "ErrorCategory")
    public String getErrorCategory() {
        return errorCategory;
    }

    public void setErrorCategory(String errorCategory) {
        this.errorCategory = errorCategory;
    }

    @XmlElement(name = "ErrorNumber")
    public String getErrorNumber() {
        return errorNumber;
    }

    public void setErrorNumber(String errorNumber) {
        this.errorNumber = errorNumber;
    }

    @XmlElement(name = "ErrorDescription")
    public String getErrorDescription() {
        return errorDescription;
    }

    public void setErrorDescription(String errorDescription) {
        this.errorDescription = errorDescription;
    }

    @XmlElement(name = "RequestId")
    public String getRequestId() {
        return requestId;
    }

    public void setRequestId(String requestId) {
        this.requestId = requestId;
    }
}
