# Option two: preliminary complete-unit ownership

{
  "strategy": "behavior_units",
  "units": [
    {
      "unit_id": "configured_step-3643d2141e0adb1bddc660d7",
      "kind": "configured_step",
      "logical_id": "NoLinksFound",
      "configuration_xml": "<opStep id=\"NoLinksFound\" implClass=\"com.ibm.il.dse.operations.common.MapErrorByValueAlways\" ErrorCategory=\"20\" ErrorNumber=\"1\" on0Return=\"ErrorBody\" onOtherDo=\"end\" />\n\n    ",
      "consumers": [
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "IVR/GetClientAccountsOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "3643d2141e0adb1bddc660d7cd996fb892f5480e097d39ba326416f3328ff0ba",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-42b95631a1866d97e7e0cbfa",
      "kind": "configured_step",
      "logical_id": "GetClientLinks",
      "configuration_xml": "<opStep id=\"GetClientLinks\" implClass=\"com.ibm.il.dse.operations.internet.db.GetClientLinksSP\" on0Do=\"end\" on4Do=\"NoLinksFound\" on8Do=\"DatabaseError\" onOtherDo=\"TechnicalError\" />\n\n    ",
      "consumers": [
        "INTERNET/GetClientLinksOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "fingerprint": "42b95631a1866d97e7e0cbfa519a8a98ab916115e1acd3954c310377bb3ab4ae",
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
      "unit_id": "request_unformat-561a01497abb3d3133b663f0",
      "kind": "request_unformat",
      "logical_id": "GetClientLinksRQFmt",
      "configuration_xml": "<fmtDef id=\"GetClientLinksRQFmt\">\n    <CCXML dataName=\"GetClientLinks\">\n      <CCString dataName=\"ClientId\" />\n      <CCMandatory />\n      <CCString dataName=\"BankId\" />\n      <CCPadding padChar=\"0\" length=\"4\" />\n    </CCXML>\n  </fmtDef>\n\n  ",
      "consumers": [
        "INTERNET/GetClientLinksOp",
        "INTERNET/GetClientOverviewOp",
        "INTERNET/ValidateClientLinksOp"
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
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCMandatory[1]"
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
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[1]"
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
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires FormatDecoratorHolder"
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
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires com.ibm.dse.base.FormatDecoratorHolder"
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
          "origin": "decorator nilDecorator: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires FormatDecoratorHolder"
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
          "origin": "decorator nilDecorator: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires com.ibm.dse.base.FormatDecoratorHolder"
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
          "origin": "formatter CCBoolean: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCBoolean[1] -> com.ibm.il.dse.cc.format.CCBoolean requires AbstractFormatElement"
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
          "origin": "formatter CCIColl: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1] -> com.ibm.il.dse.cc.format.CCIColl requires AbstractFormatElement"
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
          "origin": "formatter CCString: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/CCString[1] -> com.ibm.il.dse.cc.format.CCString requires AbstractFormatElement"
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
          "origin": "formatter CCTableFormat: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCTableFormat[1] -> com.ibm.il.dse.cc.format.CCTableFormat requires AbstractFormatElement"
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
          "origin": "formatter CCXML: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1] -> com.ibm.il.dse.cc.format.CCXML requires AbstractFormatElement"
        }
      ],
      "referenced_definitions": [],
      "fingerprint": "561a01497abb3d3133b663f0fd2af0a8b77d80b7499519d55e17960e2bdc4908",
      "schema_version": "v1"
    },
    {
      "unit_id": "response_format-5dfecf09ff9fd30503abf76e",
      "kind": "response_format",
      "logical_id": "GetClientLinksRSFmt",
      "configuration_xml": "<fmtDef id=\"GetClientLinksRSFmt\">\n    <CCXML dataName=\"GetClientLinksResponse\" transparent=\"true\">\n      <CCString dataName=\"ClientId\" />\n      <CCIColl dataName=\"Links\" times=\"*\">\n        <CCXML dataName=\"Link\">\n          <CCString dataName=\"LinkId\" />\n          <CCMandatory />\n          <CCTableFormat dataName=\"LinkDescription\" fromTable=\"LINK_TYPES\" fromColumn=\"DESCRIPTION\" keyValue=\"LinkId\" />\n          <nilDecorator />\n          <CCString dataName=\"LinkUrl\" />\n          <CCBoolean dataName=\"IsExternal\" />\n          <CCString dataName=\"IconCode\" />\n          <nilDecorator />\n        </CCXML>\n      </CCIColl>\n    </CCXML>\n  </fmtDef>\n\n  ",
      "consumers": [
        "INTERNET/GetClientLinksOp",
        "INTERNET/GetClientOverviewOp",
        "INTERNET/ValidateClientLinksOp"
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
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCMandatory[1]"
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
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[1]"
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
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires FormatDecoratorHolder"
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
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires com.ibm.dse.base.FormatDecoratorHolder"
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
          "origin": "decorator nilDecorator: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires FormatDecoratorHolder"
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
          "origin": "decorator nilDecorator: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires com.ibm.dse.base.FormatDecoratorHolder"
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
          "origin": "formatter CCBoolean: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCBoolean[1] -> com.ibm.il.dse.cc.format.CCBoolean requires AbstractFormatElement"
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
          "origin": "formatter CCIColl: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1] -> com.ibm.il.dse.cc.format.CCIColl requires AbstractFormatElement"
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
          "origin": "formatter CCString: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/CCString[1] -> com.ibm.il.dse.cc.format.CCString requires AbstractFormatElement"
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
          "origin": "formatter CCTableFormat: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCTableFormat[1] -> com.ibm.il.dse.cc.format.CCTableFormat requires AbstractFormatElement"
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
          "origin": "formatter CCXML: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1] -> com.ibm.il.dse.cc.format.CCXML requires AbstractFormatElement"
        }
      ],
      "referenced_definitions": [],
      "fingerprint": "5dfecf09ff9fd30503abf76e2aee063f9752ab84eefa251b8c01b3b7a0e9b491",
      "schema_version": "v1"
    },
    {
      "unit_id": "response_format-66bf2c108225fb63eb2a0cbe",
      "kind": "response_format",
      "logical_id": "StandardErrorRSFmt",
      "configuration_xml": "<fmtDef id=\"StandardErrorRSFmt\">\n    <CCXML dataName=\"ErrorReply\">\n      <CCString dataName=\"ErrorCategory\" />\n      <CCString dataName=\"ErrorNumber\" />\n      <CCString dataName=\"ErrorDescription\" />\n      <nilDecorator />\n      <CCString dataName=\"RequestId\" />\n    </CCXML>\n  </fmtDef>\n\n  \n  ",
      "consumers": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/GetClientOverviewOp",
        "INTERNET/TransferFundsOp",
        "INTERNET/ValidateClientLinksOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
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
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires FormatDecoratorHolder"
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
          "origin": "decorator CCPadding: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[1]/CCXML[1]/CCPadding[1] -> com.ibm.il.dse.cc.decorator.CCPadding requires com.ibm.dse.base.FormatDecoratorHolder"
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
          "origin": "decorator nilDecorator: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires FormatDecoratorHolder"
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
          "origin": "decorator nilDecorator: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/nilDecorator[1] -> com.ibm.il.dse.cc.decorator.NilDecorator requires com.ibm.dse.base.FormatDecoratorHolder"
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
          "origin": "formatter CCBoolean: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCBoolean[1] -> com.ibm.il.dse.cc.format.CCBoolean requires AbstractFormatElement"
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
          "origin": "formatter CCIColl: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1] -> com.ibm.il.dse.cc.format.CCIColl requires AbstractFormatElement"
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
          "origin": "formatter CCString: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/CCString[1] -> com.ibm.il.dse.cc.format.CCString requires AbstractFormatElement"
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
          "origin": "formatter CCTableFormat: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCTableFormat[1] -> com.ibm.il.dse.cc.format.CCTableFormat requires AbstractFormatElement"
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
          "origin": "formatter CCXML: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1] -> com.ibm.il.dse.cc.format.CCXML requires AbstractFormatElement"
        }
      ],
      "referenced_definitions": [],
      "fingerprint": "66bf2c108225fb63eb2a0cbe77cb199491fae48e91ca0ab13b0980d63f311d10",
      "schema_version": "v1"
    }
  ],
  "ownership": {
    "assignments": {
      "configured_step-3643d2141e0adb1bddc660d7": null,
      "configured_step-42b95631a1866d97e7e0cbfa": null,
      "configured_step-9d214a54d7b141366dcd456c": "shared-33e19da28f26",
      "configured_step-3a42c4326e3d7f21467b61b2": "shared-33e19da28f26",
      "request_unformat-561a01497abb3d3133b663f0": null,
      "response_format-5dfecf09ff9fd30503abf76e": null,
      "response_format-66bf2c108225fb63eb2a0cbe": "shared-725dc6e56b3b"
    },
    "consumers": {
      "configured_step-3643d2141e0adb1bddc660d7": [
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "IVR/GetClientAccountsOp"
      ],
      "configured_step-42b95631a1866d97e7e0cbfa": [
        "INTERNET/GetClientLinksOp"
      ],
      "configured_step-9d214a54d7b141366dcd456c": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/TransferFundsOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ],
      "configured_step-3a42c4326e3d7f21467b61b2": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/TransferFundsOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ],
      "request_unformat-561a01497abb3d3133b663f0": [
        "INTERNET/GetClientLinksOp",
        "INTERNET/GetClientOverviewOp",
        "INTERNET/ValidateClientLinksOp"
      ],
      "response_format-5dfecf09ff9fd30503abf76e": [
        "INTERNET/GetClientLinksOp",
        "INTERNET/GetClientOverviewOp",
        "INTERNET/ValidateClientLinksOp"
      ],
      "response_format-66bf2c108225fb63eb2a0cbe": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/GetClientOverviewOp",
        "INTERNET/TransferFundsOp",
        "INTERNET/ValidateClientLinksOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ]
    },
    "fingerprint": "27fc8d2e6d67841d8c445f277db9c4ed75aa9660aa499180e81ddb2bdce4f8bd"
  },
  "closure_ready": true
}