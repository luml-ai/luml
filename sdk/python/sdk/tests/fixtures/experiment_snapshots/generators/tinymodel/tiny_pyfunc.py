from fnnx.variants.pyfunc import PyFunc


class IdentityPyFunc(PyFunc):
    def compute(self, inputs: dict, dynamic_attributes: dict) -> dict:
        return {"y": inputs["x"]}
