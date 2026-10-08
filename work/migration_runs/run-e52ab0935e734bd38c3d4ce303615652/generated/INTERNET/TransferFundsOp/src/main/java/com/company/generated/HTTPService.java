package com.company.generated;

/** Dummy fraud backend contract converted to clean native Java. */
public class HTTPService {
    /** Return a fixed sample response for the demo fraud-detection operation. */
    public String call(String requestPayload, int timeoutMillis) throws Exception {
        return "<FraudResponse><Score>7</Score><Decision>ALLOW</Decision></FraudResponse>";
    }
}
