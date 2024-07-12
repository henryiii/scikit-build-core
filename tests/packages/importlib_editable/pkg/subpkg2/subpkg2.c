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

static PyMethodDef subpkg2_methods[] = {
    {"square", square_wrapper, METH_VARARGS, "Square function"},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef subpkg2_module = {PyModuleDef_HEAD_INIT, "subpkg2",
                                             NULL, -1, subpkg2_methods};

/* name here must match extension name, with PyInit_ prefix */
PyMODINIT_FUNC PyInit_subpkg2(void) {
  return PyModule_Create(&subpkg2_module);
}
