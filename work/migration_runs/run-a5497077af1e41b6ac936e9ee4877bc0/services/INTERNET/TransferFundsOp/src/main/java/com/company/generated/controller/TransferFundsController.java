package com.company.generated.controller;

import com.company.generated.operations.TransferFundsOpService;
import com.company.generated.units.u5ce9c9ef500c.TransferFundsRequestXml;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Objects;

@RestController
@RequestMapping(value = "/api/transfers", produces = MediaType.APPLICATION_XML_VALUE, consumes = MediaType.APPLICATION_XML_VALUE)
public class TransferFundsController {

    private final TransferFundsOpService transferFundsOpService;

    public TransferFundsController(TransferFundsOpService transferFundsOpService) {
        this.transferFundsOpService = Objects.requireNonNull(transferFundsOpService);
    }

    @PostMapping
    public String executeTransfer(@RequestBody TransferFundsRequestXml requestXml) throws Exception {
        return transferFundsOpService.execute(requestXml);
    }
}
