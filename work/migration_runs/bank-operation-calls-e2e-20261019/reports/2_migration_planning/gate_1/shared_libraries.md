# Option two: preliminary complete-unit ownership

{
  "strategy": "behavior_units",
  "units": [
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
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[1]"
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
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCMandatory[1]"
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
          "origin": "formatter CCString: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/CCString[4] -> com.ibm.il.dse.cc.format.CCString requires AbstractFormatElement"
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
          "origin": "formatter CCXML: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1] -> com.ibm.il.dse.cc.format.CCXML requires AbstractFormatElement"
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
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[1]/CCXML[1]/CCMandatory[1]"
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
          "origin": "decorator CCMandatory: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1]/CCIColl[1]/CCXML[1]/CCMandatory[1]"
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
          "origin": "formatter CCString: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/CCString[4] -> com.ibm.il.dse.cc.format.CCString requires AbstractFormatElement"
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
          "origin": "formatter CCXML: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1] -> com.ibm.il.dse.cc.format.CCXML requires AbstractFormatElement"
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
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/GetClientOverviewOp",
        "INTERNET/TransferFundsOp",
        "INTERNET/ValidateClientLinksOp"
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
          "origin": "formatter CCString: WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml /XML[1]/fmtDef[3]/CCXML[1]/CCString[4] -> com.ibm.il.dse.cc.format.CCString requires AbstractFormatElement"
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
          "origin": "formatter CCXML: WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml /XML[1]/fmtDef[2]/CCXML[1] -> com.ibm.il.dse.cc.format.CCXML requires AbstractFormatElement"
        }
      ],
      "referenced_definitions": [],
      "fingerprint": "66bf2c108225fb63eb2a0cbe77cb199491fae48e91ca0ab13b0980d63f311d10",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-15edb87ae7f68ca9aed10a8b",
      "kind": "configured_step",
      "logical_id": "ValidateClientLinksFetch",
      "configuration_xml": "<opStep id=\"ValidateClientLinksFetch\" implClass=\"com.ibm.il.dse.cc.cut.CCComplexOpStep\" opExecuteName=\"GetClientLinksOp\" on0Do=\"end\" onOtherDo=\"end\" />\n    ",
      "consumers": [
        "INTERNET/ValidateClientLinksOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "operation_calls": [
        {
          "callee": "INTERNET/GetClientLinksOp",
          "caller": "INTERNET/ValidateClientLinksOp",
          "evidence_hash": "9fa02bfacf511806fb9cb54cf4349959174eff97a45909101bfae20af276cc1d",
          "note": "opsteps\\ValidateClientLinksFetch.md",
          "parameters": {
            "opExecuteName": "GetClientLinksOp"
          },
          "step": "ValidateClientLinksFetch",
          "transitions": {
            "on0Do": "end",
            "onOtherDo": "end"
          },
          "service_contract": {
            "base_url_property": "operations.4f5f5fbdd1e3.base-url",
            "call_evidence": [],
            "error_policy": "Preserve target error XML and map evidenced return outcomes; report unknown mappings.",
            "formats": {
              "csErrorReplyFormat": {
                "markdown": "# StandardErrorRSFmt\n\n---\nentity_type: format\nentity_id: StandardErrorRSFmt\nconversion_status: not_started\nshared: true\nused_by_operations:\n  - GetAccountDetailsOp\n  - GetClientAccountsOp\n  - GetClientLinksOp\n  - GetClientOverviewOp\n  - TransferFundsOp\n  - ValidateClientLinksOp\nsource_file: C:\\GitHub\\shaybc\\snapir\\bank-demo\\composer\\Workspace\\WSBCC_XML\\src\\Xml Definition\\Channel\\XML\\defaultFile\\dseformat.xml\nsource_hash: c1896648708bc8b2fcef4dfea7b956580922d56268c6a6947c807ccec9063f52\n---\n\n## Structure\n```xml\n<CCXML dataName=\"ErrorReply\">\n  <CCString dataName=\"ErrorCategory\"/>\n  <CCString dataName=\"ErrorNumber\"/>\n  <CCString dataName=\"ErrorDescription\">\n  </CCString>\n    decorator: <nilDecorator/>\n  <CCString dataName=\"RequestId\"/>\n</CCXML>\n```\n\n\n## Referenced Tags\n- [CCXML](formats/CCXML.md)\n- [CCString](formats/CCString.md)\n- [nilDecorator](formats/nilDecorator.md)\n\n## Mapped Java Classes\n- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)\n- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)\n- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)\n\n## Inferred External Dependencies\n- None\n",
                "name": "StandardErrorRSFmt"
              },
              "csReplyFormat": {
                "markdown": "# GetClientLinksRSFmt\n\n---\nentity_type: format\nentity_id: GetClientLinksRSFmt\nconversion_status: not_started\nshared: true\nused_by_operations:\n  - GetClientLinksOp\n  - GetClientOverviewOp\n  - ValidateClientLinksOp\nsource_file: C:\\GitHub\\shaybc\\snapir\\bank-demo\\composer\\Workspace\\WSBCC_INTERNET\\src\\Xml Definition\\Channel\\INTERNET\\selfDefOper\\GetClientLinks.xml\nsource_hash: 5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88\n---\n\n## Structure\n```xml\n<CCXML dataName=\"GetClientLinksResponse\" transparent=\"true\">\n  <CCString dataName=\"ClientId\"/>\n  <CCIColl dataName=\"Links\" times=\"*\">\n    <CCXML dataName=\"Link\">\n      <CCString dataName=\"LinkId\">\n      </CCString>\n        decorator: <CCMandatory/>\n      <CCTableFormat dataName=\"LinkDescription\" fromColumn=\"DESCRIPTION\" fromTable=\"LINK_TYPES\" keyValue=\"LinkId\">\n      </CCTableFormat>\n        decorator: <nilDecorator/>\n      <CCString dataName=\"LinkUrl\"/>\n      <CCBoolean dataName=\"IsExternal\"/>\n      <CCString dataName=\"IconCode\">\n      </CCString>\n        decorator: <nilDecorator/>\n    </CCXML>\n  </CCIColl>\n</CCXML>\n```\n\n## Serialization Notes\n- This format contains CCXML serialization flags that affect the XML wire shape.\n- `GetClientLinksResponse transparent=true`\n\n## Database Lookups\n> These lookups were encoded inside the WSBCC format definition. In the converted service they must be moved to the service layer, not the serializer.\n\n- CCTableFormat: fromTable `LINK_TYPES`, fromColumn `DESCRIPTION`, keyValue `LinkId`\n\n\n## Referenced Tags\n- [CCXML](formats/CCXML.md)\n- [CCString](formats/CCString.md)\n- [CCIColl](formats/CCIColl.md)\n- [CCMandatory](formats/CCMandatory.md)\n- [CCTableFormat](formats/CCTableFormat.md)\n- [nilDecorator](formats/nilDecorator.md)\n- [CCBoolean](formats/CCBoolean.md)\n\n## Mapped Java Classes\n- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)\n- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)\n- [com.ibm.il.dse.cc.format.CCIColl](classes/com/ibm/il/dse/cc/format/CCIColl.md)\n- com.ibm.il.dse.cc.decorator.CCMandatory\n- [com.ibm.il.dse.cc.format.CCTableFormat](classes/com/ibm/il/dse/cc/format/CCTableFormat.md)\n- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)\n- [com.ibm.il.dse.cc.format.CCBoolean](classes/com/ibm/il/dse/cc/format/CCBoolean.md)\n\n## Inferred External Dependencies\n- Database\n- API/Service\n",
                "name": "GetClientLinksRSFmt"
              },
              "csRequestFormat": {
                "markdown": "# GetClientLinksRQFmt\n\n---\nentity_type: format\nentity_id: GetClientLinksRQFmt\nconversion_status: not_started\nshared: true\nused_by_operations:\n  - GetClientLinksOp\n  - GetClientOverviewOp\n  - ValidateClientLinksOp\nsource_file: C:\\GitHub\\shaybc\\snapir\\bank-demo\\composer\\Workspace\\WSBCC_INTERNET\\src\\Xml Definition\\Channel\\INTERNET\\selfDefOper\\GetClientLinks.xml\nsource_hash: 5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88\n---\n\n## Structure\n```xml\n<CCXML dataName=\"GetClientLinks\">\n  <CCString dataName=\"ClientId\">\n  </CCString>\n    decorator: <CCMandatory/>\n  <CCString dataName=\"BankId\">\n  </CCString>\n    decorator: <CCPadding length=\"4\" padChar=\"0\"/>\n</CCXML>\n```\n\n\n## Referenced Tags\n- [CCXML](formats/CCXML.md)\n- [CCString](formats/CCString.md)\n- [CCMandatory](formats/CCMandatory.md)\n- [CCPadding](formats/CCPadding.md)\n\n## Mapped Java Classes\n- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)\n- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)\n- com.ibm.il.dse.cc.decorator.CCMandatory\n- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)\n\n## Inferred External Dependencies\n- None\n",
                "name": "GetClientLinksRQFmt"
              }
            },
            "media_type": "application/xml",
            "method": "POST",
            "operation": "INTERNET/GetClientLinksOp",
            "path": "/operations/INTERNET/GetClientLinksOp",
            "source_hash": "5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88",
            "fingerprint": "3a7d77d282cb31c268b2d5826766ea647c874396187843503da3315d0e8f60b5"
          }
        }
      ],
      "fingerprint": "15edb87ae7f68ca9aed10a8b584e8505f99c17ca3325d5a05220e761fe3cd8de",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-866cbe0670f145cea023b630",
      "kind": "configured_step",
      "logical_id": "OverviewRefreshLinks",
      "configuration_xml": "<opStep id=\"OverviewRefreshLinks\" implClass=\"com.ibm.il.dse.cc.cut.CCComplexOpStep\" opExecuteName=\"GetClientLinksOp\" on0Do=\"end\" onOtherDo=\"end\" />\n    ",
      "consumers": [
        "INTERNET/GetClientOverviewOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "operation_calls": [
        {
          "callee": "INTERNET/GetClientLinksOp",
          "caller": "INTERNET/GetClientOverviewOp",
          "evidence_hash": "5080be93a7d760fbb6e945d79d7a18c784db39deaf7015811a507eb0fa288807",
          "note": "opsteps\\OverviewRefreshLinks.md",
          "parameters": {
            "opExecuteName": "GetClientLinksOp"
          },
          "step": "OverviewRefreshLinks",
          "transitions": {
            "on0Do": "end",
            "onOtherDo": "end"
          },
          "service_contract": {
            "base_url_property": "operations.4f5f5fbdd1e3.base-url",
            "call_evidence": [],
            "error_policy": "Preserve target error XML and map evidenced return outcomes; report unknown mappings.",
            "formats": {
              "csErrorReplyFormat": {
                "markdown": "# StandardErrorRSFmt\n\n---\nentity_type: format\nentity_id: StandardErrorRSFmt\nconversion_status: not_started\nshared: true\nused_by_operations:\n  - GetAccountDetailsOp\n  - GetClientAccountsOp\n  - GetClientLinksOp\n  - GetClientOverviewOp\n  - TransferFundsOp\n  - ValidateClientLinksOp\nsource_file: C:\\GitHub\\shaybc\\snapir\\bank-demo\\composer\\Workspace\\WSBCC_XML\\src\\Xml Definition\\Channel\\XML\\defaultFile\\dseformat.xml\nsource_hash: c1896648708bc8b2fcef4dfea7b956580922d56268c6a6947c807ccec9063f52\n---\n\n## Structure\n```xml\n<CCXML dataName=\"ErrorReply\">\n  <CCString dataName=\"ErrorCategory\"/>\n  <CCString dataName=\"ErrorNumber\"/>\n  <CCString dataName=\"ErrorDescription\">\n  </CCString>\n    decorator: <nilDecorator/>\n  <CCString dataName=\"RequestId\"/>\n</CCXML>\n```\n\n\n## Referenced Tags\n- [CCXML](formats/CCXML.md)\n- [CCString](formats/CCString.md)\n- [nilDecorator](formats/nilDecorator.md)\n\n## Mapped Java Classes\n- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)\n- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)\n- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)\n\n## Inferred External Dependencies\n- None\n",
                "name": "StandardErrorRSFmt"
              },
              "csReplyFormat": {
                "markdown": "# GetClientLinksRSFmt\n\n---\nentity_type: format\nentity_id: GetClientLinksRSFmt\nconversion_status: not_started\nshared: true\nused_by_operations:\n  - GetClientLinksOp\n  - GetClientOverviewOp\n  - ValidateClientLinksOp\nsource_file: C:\\GitHub\\shaybc\\snapir\\bank-demo\\composer\\Workspace\\WSBCC_INTERNET\\src\\Xml Definition\\Channel\\INTERNET\\selfDefOper\\GetClientLinks.xml\nsource_hash: 5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88\n---\n\n## Structure\n```xml\n<CCXML dataName=\"GetClientLinksResponse\" transparent=\"true\">\n  <CCString dataName=\"ClientId\"/>\n  <CCIColl dataName=\"Links\" times=\"*\">\n    <CCXML dataName=\"Link\">\n      <CCString dataName=\"LinkId\">\n      </CCString>\n        decorator: <CCMandatory/>\n      <CCTableFormat dataName=\"LinkDescription\" fromColumn=\"DESCRIPTION\" fromTable=\"LINK_TYPES\" keyValue=\"LinkId\">\n      </CCTableFormat>\n        decorator: <nilDecorator/>\n      <CCString dataName=\"LinkUrl\"/>\n      <CCBoolean dataName=\"IsExternal\"/>\n      <CCString dataName=\"IconCode\">\n      </CCString>\n        decorator: <nilDecorator/>\n    </CCXML>\n  </CCIColl>\n</CCXML>\n```\n\n## Serialization Notes\n- This format contains CCXML serialization flags that affect the XML wire shape.\n- `GetClientLinksResponse transparent=true`\n\n## Database Lookups\n> These lookups were encoded inside the WSBCC format definition. In the converted service they must be moved to the service layer, not the serializer.\n\n- CCTableFormat: fromTable `LINK_TYPES`, fromColumn `DESCRIPTION`, keyValue `LinkId`\n\n\n## Referenced Tags\n- [CCXML](formats/CCXML.md)\n- [CCString](formats/CCString.md)\n- [CCIColl](formats/CCIColl.md)\n- [CCMandatory](formats/CCMandatory.md)\n- [CCTableFormat](formats/CCTableFormat.md)\n- [nilDecorator](formats/nilDecorator.md)\n- [CCBoolean](formats/CCBoolean.md)\n\n## Mapped Java Classes\n- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)\n- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)\n- [com.ibm.il.dse.cc.format.CCIColl](classes/com/ibm/il/dse/cc/format/CCIColl.md)\n- com.ibm.il.dse.cc.decorator.CCMandatory\n- [com.ibm.il.dse.cc.format.CCTableFormat](classes/com/ibm/il/dse/cc/format/CCTableFormat.md)\n- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)\n- [com.ibm.il.dse.cc.format.CCBoolean](classes/com/ibm/il/dse/cc/format/CCBoolean.md)\n\n## Inferred External Dependencies\n- Database\n- API/Service\n",
                "name": "GetClientLinksRSFmt"
              },
              "csRequestFormat": {
                "markdown": "# GetClientLinksRQFmt\n\n---\nentity_type: format\nentity_id: GetClientLinksRQFmt\nconversion_status: not_started\nshared: true\nused_by_operations:\n  - GetClientLinksOp\n  - GetClientOverviewOp\n  - ValidateClientLinksOp\nsource_file: C:\\GitHub\\shaybc\\snapir\\bank-demo\\composer\\Workspace\\WSBCC_INTERNET\\src\\Xml Definition\\Channel\\INTERNET\\selfDefOper\\GetClientLinks.xml\nsource_hash: 5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88\n---\n\n## Structure\n```xml\n<CCXML dataName=\"GetClientLinks\">\n  <CCString dataName=\"ClientId\">\n  </CCString>\n    decorator: <CCMandatory/>\n  <CCString dataName=\"BankId\">\n  </CCString>\n    decorator: <CCPadding length=\"4\" padChar=\"0\"/>\n</CCXML>\n```\n\n\n## Referenced Tags\n- [CCXML](formats/CCXML.md)\n- [CCString](formats/CCString.md)\n- [CCMandatory](formats/CCMandatory.md)\n- [CCPadding](formats/CCPadding.md)\n\n## Mapped Java Classes\n- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)\n- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)\n- com.ibm.il.dse.cc.decorator.CCMandatory\n- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)\n\n## Inferred External Dependencies\n- None\n",
                "name": "GetClientLinksRQFmt"
              }
            },
            "media_type": "application/xml",
            "method": "POST",
            "operation": "INTERNET/GetClientLinksOp",
            "path": "/operations/INTERNET/GetClientLinksOp",
            "source_hash": "5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88",
            "fingerprint": "3a7d77d282cb31c268b2d5826766ea647c874396187843503da3315d0e8f60b5"
          }
        }
      ],
      "fingerprint": "866cbe0670f145cea023b6304fc75dc1dbdfd52d56f0d4082fa049089bc0aaa6",
      "schema_version": "v1"
    },
    {
      "unit_id": "configured_step-41def216c2ea6be54012fa7a",
      "kind": "configured_step",
      "logical_id": "OverviewValidateLinks",
      "configuration_xml": "<opStep id=\"OverviewValidateLinks\" implClass=\"com.ibm.il.dse.cc.cut.CCComplexOpStep\" opExecuteName=\"ValidateClientLinksOp\" on0Do=\"OverviewRefreshLinks\" onOtherDo=\"end\" />\n    ",
      "consumers": [
        "INTERNET/GetClientOverviewOp"
      ],
      "external_dependencies": [],
      "referenced_definitions": [],
      "operation_calls": [
        {
          "callee": "INTERNET/ValidateClientLinksOp",
          "caller": "INTERNET/GetClientOverviewOp",
          "evidence_hash": "308968b743be37657b7d1146a5c7a88662857d46d13d1c0e94062dfd53d521b6",
          "note": "opsteps\\OverviewValidateLinks.md",
          "parameters": {
            "opExecuteName": "ValidateClientLinksOp"
          },
          "step": "OverviewValidateLinks",
          "transitions": {
            "on0Do": "OverviewRefreshLinks",
            "onOtherDo": "end"
          },
          "service_contract": {
            "base_url_property": "operations.1ddd76166b6f.base-url",
            "call_evidence": [
              {
                "callee": "INTERNET/GetClientLinksOp",
                "caller": "INTERNET/ValidateClientLinksOp",
                "evidence_hash": "9fa02bfacf511806fb9cb54cf4349959174eff97a45909101bfae20af276cc1d",
                "note": "opsteps\\ValidateClientLinksFetch.md",
                "parameters": {
                  "opExecuteName": "GetClientLinksOp"
                },
                "step": "ValidateClientLinksFetch",
                "transitions": {
                  "on0Do": "end",
                  "onOtherDo": "end"
                }
              }
            ],
            "error_policy": "Preserve target error XML and map evidenced return outcomes; report unknown mappings.",
            "formats": {
              "csErrorReplyFormat": {
                "markdown": "# StandardErrorRSFmt\n\n---\nentity_type: format\nentity_id: StandardErrorRSFmt\nconversion_status: not_started\nshared: true\nused_by_operations:\n  - GetAccountDetailsOp\n  - GetClientAccountsOp\n  - GetClientLinksOp\n  - GetClientOverviewOp\n  - TransferFundsOp\n  - ValidateClientLinksOp\nsource_file: C:\\GitHub\\shaybc\\snapir\\bank-demo\\composer\\Workspace\\WSBCC_XML\\src\\Xml Definition\\Channel\\XML\\defaultFile\\dseformat.xml\nsource_hash: c1896648708bc8b2fcef4dfea7b956580922d56268c6a6947c807ccec9063f52\n---\n\n## Structure\n```xml\n<CCXML dataName=\"ErrorReply\">\n  <CCString dataName=\"ErrorCategory\"/>\n  <CCString dataName=\"ErrorNumber\"/>\n  <CCString dataName=\"ErrorDescription\">\n  </CCString>\n    decorator: <nilDecorator/>\n  <CCString dataName=\"RequestId\"/>\n</CCXML>\n```\n\n\n## Referenced Tags\n- [CCXML](formats/CCXML.md)\n- [CCString](formats/CCString.md)\n- [nilDecorator](formats/nilDecorator.md)\n\n## Mapped Java Classes\n- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)\n- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)\n- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)\n\n## Inferred External Dependencies\n- None\n",
                "name": "StandardErrorRSFmt"
              },
              "csReplyFormat": {
                "markdown": "# GetClientLinksRSFmt\n\n---\nentity_type: format\nentity_id: GetClientLinksRSFmt\nconversion_status: not_started\nshared: true\nused_by_operations:\n  - GetClientLinksOp\n  - GetClientOverviewOp\n  - ValidateClientLinksOp\nsource_file: C:\\GitHub\\shaybc\\snapir\\bank-demo\\composer\\Workspace\\WSBCC_INTERNET\\src\\Xml Definition\\Channel\\INTERNET\\selfDefOper\\GetClientLinks.xml\nsource_hash: 5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88\n---\n\n## Structure\n```xml\n<CCXML dataName=\"GetClientLinksResponse\" transparent=\"true\">\n  <CCString dataName=\"ClientId\"/>\n  <CCIColl dataName=\"Links\" times=\"*\">\n    <CCXML dataName=\"Link\">\n      <CCString dataName=\"LinkId\">\n      </CCString>\n        decorator: <CCMandatory/>\n      <CCTableFormat dataName=\"LinkDescription\" fromColumn=\"DESCRIPTION\" fromTable=\"LINK_TYPES\" keyValue=\"LinkId\">\n      </CCTableFormat>\n        decorator: <nilDecorator/>\n      <CCString dataName=\"LinkUrl\"/>\n      <CCBoolean dataName=\"IsExternal\"/>\n      <CCString dataName=\"IconCode\">\n      </CCString>\n        decorator: <nilDecorator/>\n    </CCXML>\n  </CCIColl>\n</CCXML>\n```\n\n## Serialization Notes\n- This format contains CCXML serialization flags that affect the XML wire shape.\n- `GetClientLinksResponse transparent=true`\n\n## Database Lookups\n> These lookups were encoded inside the WSBCC format definition. In the converted service they must be moved to the service layer, not the serializer.\n\n- CCTableFormat: fromTable `LINK_TYPES`, fromColumn `DESCRIPTION`, keyValue `LinkId`\n\n\n## Referenced Tags\n- [CCXML](formats/CCXML.md)\n- [CCString](formats/CCString.md)\n- [CCIColl](formats/CCIColl.md)\n- [CCMandatory](formats/CCMandatory.md)\n- [CCTableFormat](formats/CCTableFormat.md)\n- [nilDecorator](formats/nilDecorator.md)\n- [CCBoolean](formats/CCBoolean.md)\n\n## Mapped Java Classes\n- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)\n- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)\n- [com.ibm.il.dse.cc.format.CCIColl](classes/com/ibm/il/dse/cc/format/CCIColl.md)\n- com.ibm.il.dse.cc.decorator.CCMandatory\n- [com.ibm.il.dse.cc.format.CCTableFormat](classes/com/ibm/il/dse/cc/format/CCTableFormat.md)\n- [com.ibm.il.dse.cc.decorator.NilDecorator](classes/com/ibm/il/dse/cc/decorator/NilDecorator.md)\n- [com.ibm.il.dse.cc.format.CCBoolean](classes/com/ibm/il/dse/cc/format/CCBoolean.md)\n\n## Inferred External Dependencies\n- Database\n- API/Service\n",
                "name": "GetClientLinksRSFmt"
              },
              "csRequestFormat": {
                "markdown": "# GetClientLinksRQFmt\n\n---\nentity_type: format\nentity_id: GetClientLinksRQFmt\nconversion_status: not_started\nshared: true\nused_by_operations:\n  - GetClientLinksOp\n  - GetClientOverviewOp\n  - ValidateClientLinksOp\nsource_file: C:\\GitHub\\shaybc\\snapir\\bank-demo\\composer\\Workspace\\WSBCC_INTERNET\\src\\Xml Definition\\Channel\\INTERNET\\selfDefOper\\GetClientLinks.xml\nsource_hash: 5e8b0678d1d4e8c4d53ee6e1e39a933baff92bdd194e0ec8b9634c6d93faac88\n---\n\n## Structure\n```xml\n<CCXML dataName=\"GetClientLinks\">\n  <CCString dataName=\"ClientId\">\n  </CCString>\n    decorator: <CCMandatory/>\n  <CCString dataName=\"BankId\">\n  </CCString>\n    decorator: <CCPadding length=\"4\" padChar=\"0\"/>\n</CCXML>\n```\n\n\n## Referenced Tags\n- [CCXML](formats/CCXML.md)\n- [CCString](formats/CCString.md)\n- [CCMandatory](formats/CCMandatory.md)\n- [CCPadding](formats/CCPadding.md)\n\n## Mapped Java Classes\n- [com.ibm.il.dse.cc.format.CCXML](classes/com/ibm/il/dse/cc/format/CCXML.md)\n- [com.ibm.il.dse.cc.format.CCString](classes/com/ibm/il/dse/cc/format/CCString.md)\n- com.ibm.il.dse.cc.decorator.CCMandatory\n- [com.ibm.il.dse.cc.decorator.CCPadding](classes/com/ibm/il/dse/cc/decorator/CCPadding.md)\n\n## Inferred External Dependencies\n- None\n",
                "name": "GetClientLinksRQFmt"
              }
            },
            "media_type": "application/xml",
            "method": "POST",
            "operation": "INTERNET/ValidateClientLinksOp",
            "path": "/operations/INTERNET/ValidateClientLinksOp",
            "source_hash": "ddecb3d2c97fde723b10efb9dca896ff54ee73bf923a1f0343bf31199bbf5076",
            "fingerprint": "5d5527e697d84ca524f453c57d3f535df9bb33fa18bcc3d0d66d63d62783f081"
          }
        }
      ],
      "fingerprint": "41def216c2ea6be54012fa7aaa5c6371ae04c5a494512b3756a1790aa084da98",
      "schema_version": "v1"
    }
  ],
  "ownership": {
    "assignments": {
      "configured_step-3a42c4326e3d7f21467b61b2": "shared-33e19da28f26",
      "configured_step-9d214a54d7b141366dcd456c": "shared-33e19da28f26",
      "configured_step-42b95631a1866d97e7e0cbfa": null,
      "configured_step-3643d2141e0adb1bddc660d7": null,
      "request_unformat-561a01497abb3d3133b663f0": null,
      "response_format-5dfecf09ff9fd30503abf76e": null,
      "response_format-66bf2c108225fb63eb2a0cbe": "shared-26209c8451ff",
      "configured_step-15edb87ae7f68ca9aed10a8b": null,
      "configured_step-866cbe0670f145cea023b630": null,
      "configured_step-41def216c2ea6be54012fa7a": null
    },
    "consumers": {
      "configured_step-3a42c4326e3d7f21467b61b2": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/TransferFundsOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ],
      "configured_step-9d214a54d7b141366dcd456c": [
        "INTERNET/GetAccountDetailsOp",
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/TransferFundsOp",
        "IVR/GetAccountBalanceOp",
        "IVR/GetClientAccountsOp"
      ],
      "configured_step-42b95631a1866d97e7e0cbfa": [
        "INTERNET/GetClientLinksOp"
      ],
      "configured_step-3643d2141e0adb1bddc660d7": [
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
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
        "INTERNET/GetClientAccountsOp",
        "INTERNET/GetClientLinksOp",
        "INTERNET/GetClientOverviewOp",
        "INTERNET/TransferFundsOp",
        "INTERNET/ValidateClientLinksOp"
      ],
      "configured_step-15edb87ae7f68ca9aed10a8b": [
        "INTERNET/ValidateClientLinksOp"
      ],
      "configured_step-866cbe0670f145cea023b630": [
        "INTERNET/GetClientOverviewOp"
      ],
      "configured_step-41def216c2ea6be54012fa7a": [
        "INTERNET/GetClientOverviewOp"
      ]
    },
    "fingerprint": "2f39a668f8395f94dac897f2db2b5ebb091eb55ebd7fb29a3ee52eefa85bd0a1"
  },
  "closure_ready": true
}