"""Use the registered executable ladder for isolated bank-boundary acceptance trials."""
from runtime.behavior_conversion.bundle_output import validate_bundle,accept_bundle
from runtime.behavior_conversion.stage_compilation import production_compiler
from runtime.behavior_conversion.testing_contract import validate_testing_contract
from runtime.managed_projects import create_build_context


class AcceptanceTrialValidator:
    """Publish a trial candidate only after real build, JUnit and boundary verification."""
    def __init__(self,session,profile,request,directory,fresh):
        self.session,self.profile,self.request,self.directory,self.fresh=session,profile,request,directory,fresh
        self.tool=session.tool;self.last=None;self.stage_prerequisites={}
        self.compile_implementation=production_compiler(profile)

    def validate_metadata(self,bundle):
        """Check selected entry wiring against unchanged source-bound evidence."""
        self.fresh();self.session.static(bundle)

    def __call__(self,bundle,cached=False):
        self.fresh()
        files=validate_bundle(bundle,bundle.unit_contract.apis,self.request['requirements'],
            {source['identity'] for source in self.session.unit['sources']},self.profile.allowed_ibm_classes)
        validate_testing_contract(bundle,self.request['testing_contract'])
        self.session.static(bundle)
        required=sorted({path for key in self.request['requirements'] for path in bundle.coverage[key]})
        def compare(project,context,validation):
            self.last={'build_validation':validation.model_dump(mode='json')}
            self.session.compare(project,context,bundle,build_validation=self.last['build_validation'])
        validation,_=accept_bundle(self.directory,files,create_build_context,self.profile,bundle.dependencies,
            testing_contract=self.request['testing_contract'],required_tests=required,pre_publish=compare)
        self.last={'build_validation':validation}
        return self.last
