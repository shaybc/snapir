# Option two: preliminary complete-unit ownership

{
  "strategy": "behavior_units",
  "units": [
    {
      "unit_id": "configured_step-06cdcaacb2a8a3f59d355714",
      "kind": "configured_step",
      "logical_id": "CoreBankingRejected",
      "configuration_xml": "<opStep id=\"CoreBankingRejected\" implClass=\"com.ibm.il.dse.operations.common.MapErrorByValueAlways\" ErrorCategory=\"60\" ErrorNumber=\"6\" on0Return=\"ErrorBody\" onOtherDo=\"end\" />\n\n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "06cdcaacb2a8a3f59d355714d8acd4f49055b4458621a2791fcc42e3de988df2",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-3edad4d894ed99ee7fe5ae71",
      "kind": "configured_step",
      "logical_id": "SkipFraudOnTimeout",
      "configuration_xml": "<opStep id=\"SkipFraudOnTimeout\" implClass=\"com.ibm.il.dse.operations.common.SetChannelContext\" FieldName=\"FraudCheckSkipped\" FieldValue=\"true\" on0Do=\"ExecuteTransfer\" onOtherDo=\"TechnicalError\" />\n\n    \n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "3edad4d894ed99ee7fe5ae71acaf507fbec61293bf660aeb63884569b4c278dc",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-6d24746bc47ab347906af82e",
      "kind": "configured_step",
      "logical_id": "ExecuteTransfer",
      "configuration_xml": "<opStep id=\"ExecuteTransfer\" implClass=\"com.ibm.il.dse.operations.internet.db.ExecuteTransferSP\" on0Do=\"end\" on6Do=\"CoreBankingRejected\" on7Do=\"TransferAlreadyProcessed\" on8Do=\"DatabaseError\" onOtherDo=\"TechnicalError\" />\n\n    \n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "6d24746bc47ab347906af82e9ecf6a0058d68671dcffea46eb9140043915d27f",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-1bde9d232fc468f3294efa84",
      "kind": "configured_step",
      "logical_id": "DailyLimitExceeded",
      "configuration_xml": "<opStep id=\"DailyLimitExceeded\" implClass=\"com.ibm.il.dse.operations.common.MapErrorByValueAlways\" ErrorCategory=\"40\" ErrorNumber=\"3\" on0Return=\"ErrorBody\" onOtherDo=\"end\" />\n\n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "1bde9d232fc468f3294efa840c528bf0a483a40d2f357f061c3a28b98de9b194",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-b9a6a73909a9f8639bb03fb9",
      "kind": "configured_step",
      "logical_id": "TransferAlreadyProcessed",
      "configuration_xml": "<opStep id=\"TransferAlreadyProcessed\" implClass=\"com.ibm.il.dse.operations.common.MapErrorByValueAlways\" ErrorCategory=\"60\" ErrorNumber=\"7\" on0Return=\"ErrorBody\" onOtherDo=\"end\" />\n\n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "b9a6a73909a9f8639bb03fb9c0796c116189ebb629564282749cdea197b8ebec",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-f2c8754a25a6fcd6cc4ca9db",
      "kind": "configured_step",
      "logical_id": "FraudCheck",
      "configuration_xml": "<opStep id=\"FraudCheck\" implClass=\"com.ibm.il.dse.operations.internet.service.CallFraudDetection\" ServiceTimeout=\"5000\" on0Do=\"ExecuteTransfer\" on2Do=\"FraudSuspected\" onTimeoutDo=\"SkipFraudOnTimeout\" onOtherDo=\"TechnicalError\" />\n\n    \n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "f2c8754a25a6fcd6cc4ca9db8775fb000667775e49e479a715a7a0cefaf5a635",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-90e3461e522ae6dd954af290",
      "kind": "configured_step",
      "logical_id": "FraudSuspected",
      "configuration_xml": "<opStep id=\"FraudSuspected\" implClass=\"com.ibm.il.dse.operations.common.MapErrorByValueAlways\" ErrorCategory=\"50\" ErrorNumber=\"2\" on0Return=\"ErrorBody\" onOtherDo=\"end\" />\n\n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "90e3461e522ae6dd954af290ee976cc0f3ec7cc85aabe762494410920d9c1a79",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-2e52a65fe1cea8c4efb9ba82",
      "kind": "configured_step",
      "logical_id": "ValidationFailed",
      "configuration_xml": "<opStep id=\"ValidationFailed\" implClass=\"com.ibm.il.dse.operations.common.MapErrorByValueAlways\" ErrorCategory=\"10\" ErrorNumber=\"2\" on0Return=\"ErrorBody\" onOtherDo=\"end\" />\n\n    ",
      "consumers": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/TransferFundsOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "2e52a65fe1cea8c4efb9ba821b22718c674cf3795dc036d2e58d4ac609720f0d",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-87dd336469df574d0e064f34",
      "kind": "configured_step",
      "logical_id": "InsufficientFunds",
      "configuration_xml": "<opStep id=\"InsufficientFunds\" implClass=\"com.ibm.il.dse.operations.common.MapErrorByValueAlways\" ErrorCategory=\"40\" ErrorNumber=\"4\" on0Return=\"ErrorBody\" onOtherDo=\"end\" />\n\n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "87dd336469df574d0e064f3463e1710e83a09830f65bcb6f68205c540d1b3762",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-db5b1a29f676c69d7416ffa2",
      "kind": "configured_step",
      "logical_id": "ValidateTransfer",
      "configuration_xml": "<opStep id=\"ValidateTransfer\" implClass=\"com.ibm.il.dse.operations.common.ValidateInputFields\" RequiredFields=\"SourceAccount,TargetAccount,Amount,Currency,SessionToken\" on0Do=\"CheckLimits\" onOtherDo=\"ValidationFailed\" />\n\n    \n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "db5b1a29f676c69d7416ffa233a8dd3140a6baa3cb0a0865483d9d26fa7f3ca5",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-1e4c733765f028f5f1feb889",
      "kind": "configured_step",
      "logical_id": "AccountNotEligible",
      "configuration_xml": "<opStep id=\"AccountNotEligible\" implClass=\"com.ibm.il.dse.operations.common.MapErrorByValueAlways\" ErrorCategory=\"40\" ErrorNumber=\"5\" on0Return=\"ErrorBody\" onOtherDo=\"end\" />\n\n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "1e4c733765f028f5f1feb889300bcb3d39ac5c6d94a801f641a89dfc3f0b526c",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-9d214a54d7b141366dcd456c",
      "kind": "configured_step",
      "logical_id": "TechnicalError",
      "configuration_xml": "<opStep id=\"TechnicalError\" implClass=\"com.ibm.il.dse.operations.common.MapErrorByValueAlways\" ErrorCategory=\"99\" ErrorNumber=\"0\" on0Return=\"ErrorBody\" onOtherDo=\"end\" />\n\n    ",
      "consumers": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/TransferFundsOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "9d214a54d7b141366dcd456c8a164736da87f060177105fba7fc5d93ae4972e4",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-4ef069d52e8c34da08bcf72a",
      "kind": "configured_step",
      "logical_id": "CheckLimits",
      "configuration_xml": "<opStep id=\"CheckLimits\" implClass=\"com.ibm.il.dse.operations.internet.db.ValidateTransferLimitsSP\" on0Do=\"FraudCheck\" on3Do=\"DailyLimitExceeded\" on4Do=\"InsufficientFunds\" on5Do=\"AccountNotEligible\" on8Do=\"DatabaseError\" onOtherDo=\"TechnicalError\" />\n\n    \n    ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "4ef069d52e8c34da08bcf72abc0d55c29ee22d522336a8b8fa62efe0b49eeee6",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-3a42c4326e3d7f21467b61b2",
      "kind": "configured_step",
      "logical_id": "DatabaseError",
      "configuration_xml": "<opStep id=\"DatabaseError\" implClass=\"com.ibm.il.dse.operations.common.MapErrorByValueAlways\" ErrorCategory=\"99\" ErrorNumber=\"8\" on0Return=\"ErrorBody\" onOtherDo=\"end\" />\n\n    ",
      "consumers": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/TransferFundsOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "3a42c4326e3d7f21467b61b2a9282dbecb78e7508b6040376c2bb8349c7c2c43",
      "schema_version": "v1"
    },
    {
      "unit_id": "request_unformat-5ce9c9ef500cb53c8bf03e7d",
      "kind": "request_unformat",
      "logical_id": "TransferFundsRQFmt",
      "configuration_xml": "<fmtDef id=\"TransferFundsRQFmt\">\n    <CCXML dataName=\"TransferFunds\">\n      <CCString dataName=\"SourceAccount\" />\n      <CCMandatory />\n      <CCPadding padChar=\"0\" length=\"10\" />\n      <CCString dataName=\"TargetAccount\" />\n      <CCMandatory />\n      <CCPadding padChar=\"0\" length=\"10\" />\n      <NumberFormat dataName=\"Amount\" showThousandsSep=\"no\" showDecimalsSep=\"yes\" />\n      <CCMandatory />\n      <CCString dataName=\"Currency\" />\n      <CCPadding padChar=\" \" length=\"3\" />\n      <CCString dataName=\"SessionToken\" />\n      <CCMandatory />\n      <MaskLogDecorator />\n      <CCString dataName=\"TransferReference\" />\n      <nilDecorator />\n      <CCString dataName=\"ScheduledDate\" />\n      <nilDecorator />\n    </CCXML>\n  </fmtDef>\n\n  \n  \n  \n  ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [
        {
          "class_name": "com.ibm.il.dse.cc.decorator.CCMandatory",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[4]"
        },
        {
          "class_name": "com.ibm.il.dse.cc.decorator.CCMandatory",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[1]"
        },
        {
          "class_name": "com.ibm.il.dse.cc.decorator.CCMandatory",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[3]"
        },
        {
          "class_name": "com.ibm.il.dse.cc.decorator.CCMandatory",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[2]"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires com.ibm.dse.base.FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator MaskLogDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/MaskLogDecorator[1] -> com.ibm.il.dse.cc.decorator.MaskLogDecorator requires FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator MaskLogDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/MaskLogDecorator[1] -> com.ibm.il.dse.cc.decorator.MaskLogDecorator requires com.ibm.dse.base.FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator nilDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator nilDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires com.ibm.dse.base.FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCBoolean: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/CCBoolean[1] -> com.ibm.il.dse.cc.format.CCBoolean requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCDate: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/CCDate[1] -> com.ibm.il.dse.cc.format.CCDate requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCString: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCString[1] -> com.ibm.il.dse.cc.format.CCString requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCXML: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1] -> com.ibm.il.dse.cc.format.CCXML requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter NumberFormat: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/NumberFormat[2] -> com.ibm.il.dse.cc.format.NumberFormat requires AbstractFormatElement"
        }
      ],
      "referenced_definitions": [],
      "fingerprint": "5ce9c9ef500cb53c8bf03e7d2e30f779d5a7a6f8beda8ed2fb214ab7b23d6c76",
      "schema_version": "v1"
    },
    {
      "unit_id": "response_format-b5afca9c05e0bac028e66617",
      "kind": "response_format",
      "logical_id": "TransferFundsRSFmt",
      "configuration_xml": "<fmtDef id=\"TransferFundsRSFmt\">\n    <CCXML dataName=\"TransferFundsResponse\">\n      <CCString dataName=\"TransferId\" />\n      <CCString dataName=\"TransferStatus\" />\n      <CCDate dataName=\"ExecutionDate\" pattern=\"yyyyMMdd\" useSep=\"no\" fourDigYear=\"yes\" />\n      <CCTime dataName=\"ExecutionTime\" />\n      <NumberFormat dataName=\"Amount\" showThousandsSep=\"no\" showDecimalsSep=\"yes\" />\n      <CCString dataName=\"Currency\" />\n      <CCPadding padChar=\" \" length=\"3\" />\n      <CCString dataName=\"SourceAccount\" />\n      <CCPadding padChar=\"0\" length=\"10\" />\n      <CCString dataName=\"TargetAccount\" />\n      <CCPadding padChar=\"0\" length=\"10\" />\n      <NumberFormat dataName=\"NewSourceBalance\" showThousandsSep=\"no\" showDecimalsSep=\"yes\" />\n      <nilDecorator />\n      <CCBoolean dataName=\"FraudCheckSkipped\" />\n    </CCXML>\n  </fmtDef>\n\n  ",
      "consumers": [
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires com.ibm.dse.base.FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator MaskLogDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/MaskLogDecorator[1] -> com.ibm.il.dse.cc.decorator.MaskLogDecorator requires FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator MaskLogDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/MaskLogDecorator[1] -> com.ibm.il.dse.cc.decorator.MaskLogDecorator requires com.ibm.dse.base.FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator nilDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator nilDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires com.ibm.dse.base.FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCBoolean: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/CCBoolean[1] -> com.ibm.il.dse.cc.format.CCBoolean requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCDate: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/CCDate[1] -> com.ibm.il.dse.cc.format.CCDate requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCString: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCString[1] -> com.ibm.il.dse.cc.format.CCString requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCXML: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1] -> com.ibm.il.dse.cc.format.CCXML requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter NumberFormat: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/NumberFormat[2] -> com.ibm.il.dse.cc.format.NumberFormat requires AbstractFormatElement"
        }
      ],
      "referenced_definitions": [],
      "fingerprint": "b5afca9c05e0bac028e6661713ed97d7a1eea441f562bd535147f7a513774260",
      "schema_version": "v1"
    },
    {
      "unit_id": "response_format-66bf2c108225fb63eb2a0cbe",
      "kind": "response_format",
      "logical_id": "StandardErrorRSFmt",
      "configuration_xml": "<fmtDef id=\"StandardErrorRSFmt\">\n    <CCXML dataName=\"ErrorReply\">\n      <CCString dataName=\"ErrorCategory\" />\n      <CCString dataName=\"ErrorNumber\" />\n      <CCString dataName=\"ErrorDescription\" />\n      <nilDecorator />\n      <CCString dataName=\"RequestId\" />\n    </CCXML>\n  </fmtDef>\n\n  \n  ",
      "consumers": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/TransferFundsOp"
      ],
      "external_dependencies": [
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires com.ibm.dse.base.FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator MaskLogDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/MaskLogDecorator[1] -> com.ibm.il.dse.cc.decorator.MaskLogDecorator requires FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator MaskLogDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/MaskLogDecorator[1] -> com.ibm.il.dse.cc.decorator.MaskLogDecorator requires com.ibm.dse.base.FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator nilDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.dse.base.FormatDecoratorHolder",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "decorator nilDecorator: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires com.ibm.dse.base.FormatDecoratorHolder"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCBoolean: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/CCBoolean[1] -> com.ibm.il.dse.cc.format.CCBoolean requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCDate: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/CCDate[1] -> com.ibm.il.dse.cc.format.CCDate requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCString: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1]/CCString[1] -> com.ibm.il.dse.cc.format.CCString requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter CCXML: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[1]/CCXML[1] -> com.ibm.il.dse.cc.format.CCXML requires AbstractFormatElement"
        },
        {
          "class_name": "com.ibm.il.dse.cc.format.AbstractFormatElement",
          "treatment": "replace",
          "maven_coordinates": null,
          "behavior_description": "Replace Composer runtime behavior using the embedded component contracts",
          "behavior_evidence": [
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "4. Runtime Execution Model",
              "content_hash": "dee87849ddd2a8bf3ecb387db49b4302c23c852b54f4850643bb8f7c2bb63e4a"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "5. Context",
              "content_hash": "37f170488586f0f792209cd78d6f595dd1f87d9fdf777e36a9b334bed6a2cec8"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "6. Formats and the Format/Unformat Process",
              "content_hash": "8a0189fb3052b2fd2255f282277a4446377b592483378da3f02c0ffca162826c"
            },
            {
              "document": "embedded:composer_conversion_knowledge",
              "heading": "7. Decorators",
              "content_hash": "0dae02d0709a670195856f35ecba11496c6e6987d38f2be86dd13838877833fd"
            }
          ],
          "origin": "formatter NumberFormat: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml /XML[1]/fmtDef[2]/CCXML[1]/NumberFormat[2] -> com.ibm.il.dse.cc.format.NumberFormat requires AbstractFormatElement"
        }
      ],
      "referenced_definitions": [],
      "fingerprint": "66bf2c108225fb63eb2a0cbe77cb199491fae48e91ca0ab13b0980d63f311d10",
      "schema_version": "v1"
    }
  ],
  "ownership": {
    "assignments": {
      "configured_step-06cdcaacb2a8a3f59d355714": null,
      "configured_step-3edad4d894ed99ee7fe5ae71": null,
      "configured_step-6d24746bc47ab347906af82e": null,
      "configured_step-1bde9d232fc468f3294efa84": null,
      "configured_step-b9a6a73909a9f8639bb03fb9": null,
      "configured_step-f2c8754a25a6fcd6cc4ca9db": null,
      "configured_step-90e3461e522ae6dd954af290": null,
      "configured_step-2e52a65fe1cea8c4efb9ba82": "shared-aacf434ff625",
      "configured_step-87dd336469df574d0e064f34": null,
      "configured_step-db5b1a29f676c69d7416ffa2": null,
      "configured_step-1e4c733765f028f5f1feb889": null,
      "configured_step-9d214a54d7b141366dcd456c": "shared-33e19da28f26",
      "configured_step-4ef069d52e8c34da08bcf72a": null,
      "configured_step-3a42c4326e3d7f21467b61b2": "shared-33e19da28f26",
      "request_unformat-5ce9c9ef500cb53c8bf03e7d": null,
      "response_format-b5afca9c05e0bac028e66617": null,
      "response_format-66bf2c108225fb63eb2a0cbe": null
    },
    "consumers": {
      "configured_step-06cdcaacb2a8a3f59d355714": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-3edad4d894ed99ee7fe5ae71": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-6d24746bc47ab347906af82e": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-1bde9d232fc468f3294efa84": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-b9a6a73909a9f8639bb03fb9": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-f2c8754a25a6fcd6cc4ca9db": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-90e3461e522ae6dd954af290": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-2e52a65fe1cea8c4efb9ba82": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/TransferFundsOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ],
      "configured_step-87dd336469df574d0e064f34": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-db5b1a29f676c69d7416ffa2": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-1e4c733765f028f5f1feb889": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-9d214a54d7b141366dcd456c": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/TransferFundsOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ],
      "configured_step-4ef069d52e8c34da08bcf72a": [
        "INTERNET/TransferFundsOp"
      ],
      "configured_step-3a42c4326e3d7f21467b61b2": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/TransferFundsOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ],
      "request_unformat-5ce9c9ef500cb53c8bf03e7d": [
        "INTERNET/TransferFundsOp"
      ],
      "response_format-b5afca9c05e0bac028e66617": [
        "INTERNET/TransferFundsOp"
      ],
      "response_format-66bf2c108225fb63eb2a0cbe": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/TransferFundsOp"
      ]
    },
    "fingerprint": "6892b221b722127bc1186322ef15750a29b5c602f0ce19f82c43fd2eace60646"
  },
  "closure_ready": true
}