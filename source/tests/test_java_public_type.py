"""Check managed conversion filenames, Java type preservation, and native packages."""

import pytest

from runtime.java_public_type import converted_java_identity


@pytest.mark.parametrize("declaration", ["public class", "public final class", "public abstract class",
    "public interface", "public enum", "public record", "public @interface", "public sealed class"])
def test_valid_public_type_kinds(declaration):
    suffix = "()" if "record" in declaration else ""
    source = f"package com.company.generated.demo; {declaration} Example{suffix} {{}}"
    assert converted_java_identity(source) == ("com.company.generated.demo", "Example")


def test_comments_literals_and_nested_types_do_not_change_filename():
    source = '''package com.company.generated;
    // public class FalseName {}
    public class Example {
      String text = "public class Fake {}";
      public interface Nested {}
    }'''
    assert converted_java_identity(source)[1] == "Example"


def test_multiple_public_types_rejected():
    with pytest.raises(ValueError, match="exactly one public top-level"):
        converted_java_identity("package com.company.generated; public class A {} public interface B {}")


@pytest.mark.parametrize("package", ["com.ibm.dse.base", "com.example", "com.company.generatedOther", ""])
def test_non_native_packages_rejected(package):
    source = (f"package {package};" if package else "") + "public abstract class Example {}"
    with pytest.raises(ValueError, match="native destination package"):
        converted_java_identity(source)


def test_original_class_cannot_be_replaced_with_interface():
    with pytest.raises(ValueError, match="changed the original public class"):
        converted_java_identity("package com.company.generated; public interface Example {}",
                                "package com.ibm.old; public class Example { public void execute() {} }")


def test_original_interface_and_abstract_class_are_supported():
    for kind in ("interface", "abstract class"):
        assert converted_java_identity(f"package com.company.generated; public {kind} Example {{}}",
                                       f"package com.ibm.old; public {kind} Example {{}}")[1] == "Example"
