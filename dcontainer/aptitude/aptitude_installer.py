from typing import List, Optional, Dict

from dcontainer.utils.invoker import Invoker


class AptitudeInstaller:

    class InstallAptitude(Exception):
        pass

    class PPASOnNonUbuntu(Exception):
        pass

    class AptUpdateFailed(Invoker.InvokerException):
        pass

    class AddPPAsFailed(Invoker.InvokerException):
        pass

    class RemovePPAsFailed(Invoker.InvokerException):
        pass

    class CleanUpFailed(Invoker.InvokerException):
        pass
    

    @staticmethod
    def normalize_ppas(ppas: List[str]) -> List[str]:
        # normalize ppas to have the ppa: initials
        for ppa_idx, ppa in enumerate(ppas):
            if "ppa:" != ppa[:4]:
                ppas[ppa_idx] = f"ppa:{ppa}"
        return ppas
    
    @staticmethod
    def _parse_env_file(path: str) -> Dict[str,str]:
        with open(path, 'r') as f:                                               
            return dict(tuple(line.replace('\n', '').split('=')) for line in f.readlines() if not line.startswith('#'))
        

    @classmethod
    def is_ubuntu(cls) -> bool:
        Invoker.check_root_privileges()
        parsed_os_release = cls._parse_env_file("/etc/os-release")
        return "ubuntu" in parsed_os_release['NAME'].lower()
         
    @classmethod
    def install(
        cls,
        packages: List[str],
        ppas: Optional[List[str]] = None,
        force_ppas_on_non_ubuntu: bool = False,
        remove_ppas_on_completion: bool = True,
        remove_cache_on_completion: bool = True,
    ) -> None:

        if (
            ppas
            and not cls.is_ubuntu()
            and not force_ppas_on_non_ubuntu
        ):
            raise cls.PPASOnNonUbuntu()

        normalized_ppas = cls.normalize_ppas(ppas)
        software_properties_common_installed = False
        try:
            Invoker.invoke(
                command="apt update -y",
                raise_on_failure=True,
                exception_class=cls.AptUpdateFailed,
            )
            
            # ensure aptitude existance
            if Invoker.invoke("dpkg -s aptitude",
                raise_on_failure=False) != 0:

                Invoker.invoke(
                        command="apt-get install -y aptitude",
                        raise_on_failure=True,
                        exception_class=cls.InstallAptitude,
                    )


            if ppas:
                if Invoker.invoke("dpkg -s software-properties-common",
                                  raise_on_failure=False) != 0:
                    
                    Invoker.invoke(
                        command="aptitude install -y software-properties-common",
                        raise_on_failure=True,
                        exception_class=cls.AddPPAsFailed,
                    )

                    software_properties_common_installed = True


                for ppa in normalized_ppas:
                    Invoker.invoke(
                        command=f"add-apt-repository -y {ppa}",
                        raise_on_failure=True,
                        exception_class=cls.AddPPAsFailed,
                    )

                Invoker.invoke(
                    command="aptitude update -y",
                    raise_on_failure=True,
                    exception_class=cls.AptUpdateFailed,
                )

            Invoker.invoke(
                command=f"aptitude install -y {' '.join(packages)}",
                raise_on_failure=True,
                exception_class=cls.AptUpdateFailed,
            )

        finally:
            if remove_ppas_on_completion:
                for ppa in normalized_ppas:
                    Invoker.invoke(
                        command=f"add-apt-repository -y --remove {ppa}",
                        raise_on_failure=True,
                        exception_class=cls.RemovePPAsFailed,
                    )
                if software_properties_common_installed:
                    Invoker.invoke(
                        command="aptitude -y remove software-properties-common",
                        raise_on_failure=True,
                        exception_class=cls.RemovePPAsFailed,
                    )

            if remove_cache_on_completion:
                Invoker.invoke(
                    command="rm -rf /var/lib/apt/lists/*",
                    raise_on_failure=True,
                    exception_class=cls.CleanUpFailed,
                )