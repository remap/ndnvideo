/*
 * File:   access.h
 * Author: takeda
 *
 * Created on October 30, 2011, 6:44 PM
 */

#ifndef ACCESS_H
#  define	ACCESS_H

#  define JUMP_IF_ERR(label) \
do { \
	if (PyErr_Occurred()) \
		goto label; \
} while (0)

#  define JUMP_IF_NULL(variable, label) \
do { \
	if (!variable) \
		goto label; \
} while (0)

#  define JUMP_IF_NULL_MEM(variable, label) \
do { \
	if (!variable) { \
		PyErr_NoMemory(); \
		goto label; \
	} \
} while (0)

#  define JUMP_IF_NEG(variable, label) \
do { \
	if (variable < 0) \
		goto label; \
} while (0)

#  define JUMP_IF_NEG_MEM(variable, label) \
do { \
	if (variable < 0) { \
		PyErr_NoMemory(); \
		goto label; \
	} \
} while (0)

#endif	/* ACCESS_H */

