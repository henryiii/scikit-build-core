Name:           python-scikit-build-core
Version:        0.0.0
Release:        %autorelease
Summary:        Build backend for CMake based projects

License:        Apache-2.0
URL:            https://github.com/scikit-build/scikit-build-core
Source:         %{pypi_source scikit_build_core}

BuildArch:      noarch
BuildRequires:  python3-devel
# Testing dependences
BuildRequires:  cmake
BuildRequires:  ninja-build
BuildRequires:  gcc
BuildRequires:  gcc-c++
BuildRequires:  git

%global _description %{expand:
A next generation Python CMake adaptor and Python API for plugins
}

%description %_description

%package -n python3-scikit-build-core
Summary:        %{summary}
Requires:       cmake
Recommends:     (ninja-build or make)
Recommends:     python3-scikit-build-core+pyproject
Recommends:     python3-scikit-build-core+cli
Suggests:       ninja-build
Suggests:       gcc
%description -n python3-scikit-build-core %_description

%pyproject_extras_subpkg -n python3-scikit-build-core pyproject
%pyproject_extras_subpkg -n python3-scikit-build-core cli -F


%prep
%autosetup -n scikit_build_core-%{version}


%generate_buildrequires
%pyproject_buildrequires -x test,test-meta,test-numpy


%build
%pyproject_wheel


%install
%pyproject_install
%pyproject_save_files scikit_build_core


%check
%pytest \
    -m "not network"


%files -n python3-scikit-build-core -f %{pyproject_files}
%license LICENSE
%doc README.md
%exclude %{python3_sitelib}/scikit_build_core/__main__.py

%files -n python3-scikit-build-core+cli -f %{_pyproject_ghost_distinfo}
%{python3_sitelib}/scikit_build_core/__main__.py
%{_bindir}/skbuild


%changelog
%autochangelog
