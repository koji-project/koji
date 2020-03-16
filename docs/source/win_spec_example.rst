=========================
Example Windows Spec File
=========================

The following is an example ini-format spec file for a :doc:`Windows build <winbuild>` in Koji.

.. code-block:: ini

    [naming]
    ; naming and versioning of the component
    name = qpid-cpp-win
    version = 2.0.0.1
    release = 1
    description = Windows build of qpid-cpp-mrg

    [building]
    ; use os-arch
    platform = w2k8r2-x64

    ; file, directories, and commands that must be available in the build environment
    preinstalled = /cygdrive/c/Program Files/7-Zip/7z.exe
                   /cygdrive/c/Program Files (x86)/CMake 2.8/bin/cmake.exe
                   /cygdrive/c/Python26/python.exe
                   /cygdrive/c/Ruby186/bin/ruby.exe
                   C:\Ruby186\bin\msvcrt-ruby18.dll
                   /cygdrive/c/Program Files (x86)/doxygen/bin/doxygen.exe
                   /cygdrive/c/Program Files (x86)/Microsoft Visual Studio 9.0/Common7/IDE/devenv.exe
                   cpio
                   tar
                   patch
                   powershell

    ; To specify other components you need fetched to be able to build this, fill in a white-space
    ; delimited list of the other components you need by their names. Specific versions are not
    ; yet supported, the latest tagged will always be fetched.
    buildrequires = boost-win
                    qpid-cpp-mrg:type=rpm:arches=src

    ; what does this package provide?
    provides = qpid-cpp-win

    ; what shell are we running the commands below in?
    shell = bash

    ; what should we execute to build it?
    execute = read MAJOR MINOR REVISION BUILD < <(echo $version | tr . " ")
              pushd $boost_win_dir
              mkdir dist
              cd dist
              for z in ../boost-win-*.tar.bz2; do
                  tar xjf $z
              done
              popd
              PATH="/cygdrive/c/Program Files/7-Zip:$PATH"
              PATH="/cygdrive/c/Program Files (x86)/CMake 2.8/bin:$PATH"
              PATH="/cygdrive/c/Python26:$PATH"
              PATH="/cygdrive/c/Ruby186/bin:$PATH"
              PATH="/cygdrive/c/Program Files (x86)/doxygen/bin:$PATH"
              PATH="/cygdrive/c/Program Files (x86)/Microsoft Visual Studio 9.0/Common7/IDE:$PATH"
              export PATH
              # extract the tarball from the qpid-cpp-mrg rpm
              pushd $qpid_cpp_mrg_rpm_dir/src
              7z x qpid-cpp-*.src.rpm
              cpio -idmv < qpid-cpp-*.cpio
              popd
              mkdir source
              cd source
              tar xzf $qpid_cpp_mrg_rpm_dir/src/qpid-cpp-*.tar.gz
              cd qpid-cpp-*
              # apply patches
              for p in ../../*.patch; do
                  patch -p1 --fuzz=0 < $p
              done
              cd cpp
              cat <<EOF >> src/CMakeWinVersions.cmake
              set("winver_FILE_VERSION_N1" "$MAJOR")
              set("winver_FILE_VERSION_N2" "$MINOR")
              set("winver_FILE_VERSION_N3" "$REVISION")
              set("winver_FILE_VERSION_N4" "$BUILD")
              set("winver_PRODUCT_VERSION_N1" "$MAJOR")
              set("winver_PRODUCT_VERSION_N2" "$MINOR")
              set("winver_PRODUCT_VERSION_N3" "$REVISION")
              set("winver_PRODUCT_VERSION_N4" "$BUILD")
              EOF
              powershell -ExecutionPolicy unrestricted -File bld-winsdk.ps1 $(basename $(dirname $PWD)) $(cygpath -wa $boost_win_dir/dist/boost-win-*-32bit) $(cygpath -wa $boost_win_dir/dist/boost-win-*-64bit) $version
              mv ../../x86/qpid-cpp-x86-$version.zip ../../x64/qpid-cpp-x64-$version.zip ../../../

    ; list of files that must be present after the build for the build to be
    ; considered successful, but are not included in the list of build output
    postbuild =

    [files]
    ; all values in this section may be multi-line
    ; output files we're concerned with (specify paths relative to scm root)
    output = qpid-cpp-x86-$version.zip:i386:chk,fre
             qpid-cpp-x64-$version.zip:x86_64:chk,fre

    ; logs we should report
    logs =
