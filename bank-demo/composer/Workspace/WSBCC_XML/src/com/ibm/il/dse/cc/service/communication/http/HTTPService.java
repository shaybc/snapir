package com.ibm.il.dse.cc.service.communication.http;

/** Dummy fraud backend contract included in the bank demo's conversion input. */
public class HTTPService {
    /** Return a fixed sample response for the demo fraud-detection operation. */
    public String call(String requestPayload, int timeoutMillis) throws Exception {
        return "<FraudResponse><Score>7</Score><Decision>ALLOW</Decision></FraudResponse>";
    }
}
