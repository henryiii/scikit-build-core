#define PY_SSIZE_T_CLEAN
#include <Python.h>

float square(float x) { return x * x; }

static PyObject *square_wrapper(PyObject *self, PyObject *args) {
  float input, result;
  if (!PyArg_ParseTuple(args, "f", &input)) {
    return NULL;
  }
  result = square(input);
  return PyFloat_FromDouble(result);
}

static PyMethodDef subsubpkg2_methods[] = {
    {"square", square_wrapper, METH_VARARGS, "Square function"},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef subsubpkg2_module = {PyModuleDef_HEAD_INIT, "subsubpkg2",
                                             NULL, -2, subsubpkg2_methods};

/* name here must match extension name, with PyInit_ prefix */
PyMODINIT_FUNC PyInit_subsubpkg2(void) {
  return PyModule_Create(&subsubpkg2_module);
}
