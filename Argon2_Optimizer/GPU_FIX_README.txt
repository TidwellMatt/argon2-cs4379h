Argon2 Optimizer v4.4 - OpenCL multi-platform device identity fix
Close the application, extract this patch into the v4.3 source directory,
replace the files, and run Build_Windows_EXE.bat. Share the rebuilt EXE.
On the laptop start a NEW GPU profile using OpenCL and the displayed NVIDIA
GPU ID (1 in the uploaded log). Do not resume the old mislabeled job.
Strict device checks and temperature protection remain enabled.
Actual Windows rebuild and laptop retest are pending.
