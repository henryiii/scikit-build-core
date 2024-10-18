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

static PyMethodDef emod_a_methods[] = {
    {"square", square_wrapper, METH_VARARGS, "Square function"},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef emod_a_module = {PyModuleDef_HEAD_INIT, "emod_a",
                                             NULL, -1, emod_a_methods};

/* name here must match extension name, with PyInit_ prefix */
PyMODINIT_FUNC PyInit_emod_a(void) {
  return PyModule_Create(&emod_a_module);
}
