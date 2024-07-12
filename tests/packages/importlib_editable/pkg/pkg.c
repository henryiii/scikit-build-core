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

static PyMethodDef pkg_methods[] = {
    {"square", square_wrapper, METH_VARARGS, "Square function"},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef pkg_module = {PyModuleDef_HEAD_INIT, "pkg",
                                             NULL, -1, pkg_methods};

/* name here must match extension name, with PyInit_ prefix */
PyMODINIT_FUNC PyInit_pkg(void) {
  return PyModule_Create(&pkg_module);
}
