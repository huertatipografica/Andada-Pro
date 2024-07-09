import os
import glob

from fontTools.misc.loggingTools import LogMixin
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor, RuleDescriptor, InstanceDescriptor

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

# Reader that parses Superpolator documents and buidls designspace objects.
# Note: the Superpolator document format precedes the designspace documnt format.
# For now I just want to migrate data out of Superpolator into designspace.
# So not all data will migrate, just the stuff we can use. 

"""


  <lib>
    <dict>
      <key>com.letterror.skateboard.interactionSources</key>
      <dict>
        <key>horizontal</key>
        <array/>
        <key>ignore</key>
        <array/>
        <key>vertical</key>
        <array/>
      </dict>
      <key>com.letterror.skateboard.mutedSources</key>
      <array>
        <array>
          <string>IBM Plex Sans Condensed-Bold.ufo</string>
          <string>foreground</string>
        </array>
      </array>
      <key>com.letterror.skateboard.previewLocation</key>
      <dict>
        <key>weight</key>
        <real>0.0</real>
      </dict>
      <key>com.letterror.skateboard.previewText</key>
      <string>SKATE</string>
    </dict>
  </lib>



"""

superpolatorDataLibKey = "com.superpolator.data"    # lib key for Sp data in .designspace
skateboardInteractionSourcesKey = "com.letterror.skateboard.interactionSources"
skateboardMutedSourcesKey = "com.letterror.skateboard.mutedSources"
skipExportKey = "public.skipExportGlyphs"
skateboardPreviewLocationsKey = "com.letterror.skateboard.previewLocation"
skateboardPreviewTextKey = "com.letterror.skateboard.previewText"

class SuperpolatorReader(LogMixin):
    ruleDescriptorClass = RuleDescriptor
    axisDescriptorClass = AxisDescriptor
    sourceDescriptorClass = SourceDescriptor
    instanceDescriptorClass = InstanceDescriptor

    def __init__(self, documentPath, documentObject, convertRules=True, convertData=True, anisotropic=False):
        self.path = documentPath
        self.documentObject = documentObject
        self.convertRules = convertRules
        self.convertData = convertData
        self.allowAnisotropic = anisotropic # maybe add conversion options later
        tree = ET.parse(self.path)
        self.root = tree.getroot()
        self.documentObject.formatVersion = self.root.attrib.get("format", "3.0")
        self.axisDefaults = {}
        self._strictAxisNames = True


    @classmethod
    def fromstring(cls, string, documentObject):
        f = BytesIO(tobytes(string, encoding="utf-8"))
        self = cls(f, documentObject)
        self.path = None
        return self

    def read(self):
        self.readAxes()
        if self.convertData:
            self.readData()
        if self.convertRules:
            self.readOldRules()
            self.readSimpleRules()
        self.readSources()
        self.readInstances()

    def readData(self):
        # read superpolator specific data, view prefs etc.
        # if possible convert it to skateboard
        interactionSources = {'horizontal': [], 'vertical': [], 'ignore': []}
        ignoreElements = self.root.findall(".ignore")
        ignoreGlyphs = []
        for ignoreElement in ignoreElements:
            names = ignoreElement.attrib.get('glyphs')
            if names:
                ignoreGlyphs = names.split(",")
        if ignoreGlyphs:
            self.documentObject.lib[skipExportKey] = ignoreGlyphs
        dataElements = self.root.findall(".data")
        if not dataElements:
            return
        newLib = {}
        interactionSourcesAdded = False
        for dataElement in dataElements:
            name = dataElement.attrib.get('name')
            value = dataElement.attrib.get('value')
            if value in ['True', 'False']:
                value = value == "True"
            else:
                try:
                    value = float(value)
                except ValueError:
                    pass
            if name == "previewtext":
                self.documentObject.lib[skateboardPreviewTextKey] = value
            elif name == "horizontalPreviewAxis":
                interactionSources['horizontal'].append(value)
                interactionSourcesAdded = True
            elif name == "verticalPreviewAxis":
                interactionSources['vertical'].append(value)
                interactionSourcesAdded = True
                            
            newLib[name] = value
        if interactionSourcesAdded:
            self.documentObject.lib[skateboardInteractionSourcesKey] = interactionSources
        if newLib:
            self.documentObject.lib[superpolatorDataLibKey] = newLib


    def readOldRules(self):
        # read the old rules
        # <rule enabled="1" logic="all" resultfalse="B" resulttrue="B.round">
        #   <condition axisname="AxisWidth" operator="==" xvalue="100.000000"/>
        # </rule>

        # superpolator old rule to simple rule
        # if op in ['<', '<=']:
        #     # old style data
        #     axes[axisName]['maximum'] = conditionDict['values']
        #     newRule.name = "converted %s < and <= "%(axisName)
        # elif op in ['>', '>=']:
        #     # old style data
        #     axes[axisName]['minimum'] = conditionDict['values']
        #     newRule.name = "converted %s > and >= "%(axisName)
        # elif op == "==":
        #     axes[axisName]['maximum'] = conditionDict['values']
        #     axes[axisName]['minimum'] = conditionDict['values']
        #     newRule.name = "converted %s == "%(axisName)
        #     newRule.enabled = False
        # elif op == "!=":
        #     axes[axisName]['maximum'] = conditionDict['values']
        #     axes[axisName]['minimum'] = conditionDict['values']
        #     newRule.name = "unsupported %s != "%(axisName)
        #     newRule.enabled = False
        # else:
        #     axes[axisName]['maximum'] = conditionDict['minimum']
        #     axes[axisName]['minimum'] = conditionDict['maximum']
        #     newRule.name = "minmax legacy rule for %s"%axisName
        #     newRule.enabled = False

        rules = []
        for oldRuleElement in self.root.findall(".rule"):
            ruleObject = self.ruleDescriptorClass()
            # only one condition set in these old rules
            cds = []
            a = oldRuleElement.attrib['resultfalse']
            b = oldRuleElement.attrib['resulttrue']
            ruleObject.subs.append((a,b))
            for oldConditionElement in oldRuleElement.findall(".condition"):
                cd = {}
                operator = oldConditionElement.attrib['operator']
                axisValue = float(oldConditionElement.attrib['xvalue'])
                axisName = oldConditionElement.attrib['axisname']
                if operator in ['<', '<=']:
                    cd['maximum'] = axisValue
                    cd['minimum'] = None
                    cd['name'] = axisName
                    ruleObject.name = "converted %s < and <= "%(axisName)
                elif operator in ['>', '>=']:
                    cd['maximum'] = None
                    cd['minimum'] = axisValue
                    cd['name'] = axisName
                    ruleObject.name = "converted %s > and >= "%(axisName)
                elif operator in ["==", "!="]:
                    # can't convert this one
                    continue
                cds.append(cd)
            if cds:
                ruleObject.conditionSets.append(cds)
                self.documentObject.addRule(ruleObject)

    def readSimpleRules(self):
        # read the simple rule elements
        # <simplerules>
        #     <simplerule enabled="1" name="width: &lt; 500.0">
        #         <sub name="I" with="I.narrow"/>
        #         <condition axisname="width" maximum="500"/>
        #         <condition axisname="grade" minimum="0" maximum="500"/>
        #     </simplerule>
        # </simplerules>


        rulesContainerElements = self.root.findall(".simplerules")
        rules = []
        for rulesContainerElement in rulesContainerElements:
            for ruleElement in rulesContainerElement:
                ruleObject = self.ruleDescriptorClass()
                ruleName = ruleObject.name = ruleElement.attrib['name']
                # subs
                for subElement in ruleElement.findall('.sub'):
                    a = subElement.attrib['name']
                    b = subElement.attrib['with']
                    ruleObject.subs.append((a, b))
                # condition sets, .sp3 had none
                externalConditions = self._readConditionElements(
                    ruleElement,
                    ruleName,
                )
                if externalConditions:
                    ruleObject.conditionSets.append(externalConditions)
                    self.log.info(
                        "Found stray rule conditions outside a conditionset. "
                        "Wrapped them in a new conditionset."
                    )
                self.documentObject.addRule(ruleObject)

    def _readConditionElements(self, parentElement, ruleName=None):
        # modified from the method from fonttools.designspaceLib
        # it's not the same!
        cds = []
        for conditionElement in parentElement.findall('.condition'):
            cd = {}
            cdMin = conditionElement.attrib.get("minimum")
            if cdMin is not None:
                cd['minimum'] = float(cdMin)
            else:
                # will allow these to be None, assume axis.minimum
                cd['minimum'] = None
            cdMax = conditionElement.attrib.get("maximum")
            if cdMax is not None:
                cd['maximum'] = float(cdMax)
            else:
                # will allow these to be None, assume axis.maximum
                cd['maximum'] = None
            cd['name'] = conditionElement.attrib.get("axisname")
            # # test for things
            if cd.get('minimum') is None and cd.get('maximum') is None:
                raise DesignSpaceDocumentError(
                    "condition missing required minimum or maximum in rule" +
                    (" '%s'" % ruleName if ruleName is not None else ""))
            cds.append(cd)
        return cds

    def readAxes(self):
        # read the axes elements, including the warp map.
        axisElements = self.root.findall(".axis")
        if not axisElements:
            # raise error, we need axes
            return
        for axisElement in axisElements:
            axisObject = self.axisDescriptorClass()
            axisObject.name = axisElement.attrib.get("name")
            axisObject.tag = axisElement.attrib.get("shortname")
            axisObject.minimum = float(axisElement.attrib.get("minimum"))
            axisObject.maximum = float(axisElement.attrib.get("maximum"))
            axisObject.default = float(axisElement.attrib.get("initialvalue", axisObject.minimum))
            self.documentObject.axes.append(axisObject)
            self.axisDefaults[axisObject.name] = axisObject.default
        self.documentObject.defaultLoc = self.axisDefaults

    def colorFromElement(self, element):
        elementColor = None
        for colorElement in element.findall('.color'):
            elementColor = self.readColorElement(colorElement)

    def readColorElement(self, colorElement):
        pass

    def locationFromElement(self, element):
        elementLocation = None
        for locationElement in element.findall('.location'):
            elementLocation = self.readLocationElement(locationElement)
            break
        if not self.allowAnisotropic:
            # don't want any anisotropic values here
            split = {}
            for k, v in elementLocation.items():
                if type(v) == type(()):
                    split[k] = v[0]
                else:
                    split[k] = v
            elementLocation = split
        return elementLocation

    def readLocationElement(self, locationElement):
        """ Format 0 location reader """
        if self._strictAxisNames and not self.documentObject.axes:
            raise DesignSpaceDocumentError("No axes defined")
        loc = {}
        for dimensionElement in locationElement.findall(".dimension"):
            dimName = dimensionElement.attrib.get("name")
            if self._strictAxisNames and dimName not in self.axisDefaults:
                # In case the document contains no axis definitions,
                self.log.warning("Location with undefined axis: \"%s\".", dimName)
                continue
            xValue = yValue = None
            try:
                xValue = dimensionElement.attrib.get('xvalue')
                xValue = float(xValue)
            except ValueError:
                self.log.warning("KeyError in readLocation xValue %3.3f", xValue)
            try:
                yValue = dimensionElement.attrib.get('yvalue')
                if yValue is not None:
                    yValue = float(yValue)
            except ValueError:
                pass
            if yValue is not None:
                loc[dimName] = (xValue, yValue)
            else:
                loc[dimName] = xValue
        return loc

    def readSources(self):
        for sourceCount, sourceElement in enumerate(self.root.findall(".master")):
            filename = sourceElement.attrib.get('filename')
            if filename is not None and self.path is not None:
                sourcePath = os.path.abspath(os.path.join(os.path.dirname(self.path), filename))
            else:
                sourcePath = None
            sourceName = sourceElement.attrib.get('name')
            if sourceName is None:
                # add a temporary source name
                sourceName = "temp_master.%d" % (sourceCount)
            sourceObject = self.sourceDescriptorClass()
            sourceObject.path = sourcePath        # absolute path to the ufo source
            sourceObject.filename = filename      # path as it is stored in the document
            sourceObject.name = sourceName
            familyName = sourceElement.attrib.get("familyname")
            if familyName is not None:
                sourceObject.familyName = familyName
            styleName = sourceElement.attrib.get("stylename")
            if styleName is not None:
                sourceObject.styleName = styleName
            sourceObject.location = self.locationFromElement(sourceElement)
            isMuted = False
            for maskedElement in sourceElement.findall('.maskedfont'):
                # mute isn't stored in the sourceDescriptor, but we can store it in the lib
                if maskedElement.attrib.get('font') == "1":
                    isMuted = True
            for libElement in sourceElement.findall('.provideLib'):
                if libElement.attrib.get('state') == '1':
                    sourceObject.copyLib = True
            for groupsElement in sourceElement.findall('.provideGroups'):
                if groupsElement.attrib.get('state') == '1':
                    sourceObject.copyGroups = True
            for infoElement in sourceElement.findall(".provideInfo"):
                if infoElement.attrib.get('state') == '1':
                    sourceObject.copyInfo = True
            for featuresElement in sourceElement.findall(".provideFeatures"):
                if featuresElement.attrib.get('state') == '1':
                    sourceObject.copyFeatures = True
            for glyphElement in sourceElement.findall(".glyph"):
                glyphName = glyphElement.attrib.get('name')
                if glyphName is None:
                    continue
                if glyphElement.attrib.get('mute') == '1':
                    sourceObject.mutedGlyphNames.append(glyphName)
            self.documentObject.sources.append(sourceObject)
            if isMuted:
                if not skateboardMutedSourcesKey in self.documentObject.lib:
                    self.documentObject.lib[skateboardMutedSourcesKey] = []
                item = (sourceObject.filename, "foreground")
                self.documentObject.lib[skateboardMutedSourcesKey].append(item)

    def readInstances(self):
        for instanceCount, instanceElement in enumerate(self.root.findall(".instance")):
            instanceObject = self.instanceDescriptorClass()
            if instanceElement.attrib.get("familyname"):
                instanceObject.familyName = instanceElement.attrib.get("familyname")
            if instanceElement.attrib.get("stylename"):
                instanceObject.styleName = instanceElement.attrib.get("stylename")
            if instanceElement.attrib.get("styleMapFamilyName"):
                instanceObject.styleMapFamilyName = instanceElement.attrib.get("styleMapFamilyName")
            if instanceElement.attrib.get("styleMapStyleName"):
                instanceObject.styleMapStyleName = instanceElement.attrib.get("styleMapStyleName")
            if instanceElement.attrib.get("styleMapFamilyName"):
                instanceObject.styleMapFamilyName = instanceElement.attrib.get("styleMapFamilyName")
            instanceObject.location = self.locationFromElement(instanceElement)
            instanceObject.filename = instanceElement.attrib.get('filename')
            for libElement in instanceElement.findall('.provideLib'):
                if libElement.attrib.get('state') == '1':
                    instanceObject.lib = True
            for libElement in instanceElement.findall('.provideInfo'):
                if libElement.attrib.get('state') == '1':
                    instanceObject.info = True
            self.documentObject.instances.append(instanceObject)

def sp3_to_designspace(sp3path, designspacePath=None):
    if designspacePath is None:
        designspacePath = sp3path.replace(".sp3", ".designspace")
    doc = DesignSpaceDocument()
    reader = SuperpolatorReader(sp3path, doc)
    reader.read()
    doc.write(designspacePath)


if __name__ == "__main__":

    def test_superpolator_testdoc1():
        # read superpolator_testdoc1.sp3
        # and test all the values
        testDoc = DesignSpaceDocument()
        testPath = "../../Tests/spReader_testdocs/superpolator_testdoc1.sp3"
        reader = SuperpolatorReader(testPath, testDoc)
        reader.read()

        # check the axes
        names = [a.name for a in reader.documentObject.axes]
        names.sort()
        assert names == ['grade', 'space', 'weight', 'width']
        tags = [a.tag for a in reader.documentObject.axes]
        tags.sort()
        assert tags == ['SPCE', 'grad', 'wdth', 'wght']

        # check the data items
        assert superpolatorDataLibKey in reader.documentObject.lib
        items = list(reader.documentObject.lib[superpolatorDataLibKey].items())
        items.sort()
        assert items == [('expandRules', False), ('horizontalPreviewAxis', 'width'), ('includeLegacyRules', False), ('instancefolder', 'instances'), ('keepWorkFiles', True), ('lineInverted', True), ('lineStacked', 'lined'), ('lineViewFilled', True), ('outputFormatUFO', 3.0), ('previewtext', 'VA'), ('roundGeometry', False), ('verticalPreviewAxis', 'weight')]

        # check the sources
        for sd in reader.documentObject.sources:
            assert sd.familyName == "MutatorMathTest_SourceFamilyName"
            if sd.styleName == "Default":
                assert sd.location == {'width': 0.0, 'weight': 0.0, 'space': 0.0, 'grade': -0.5}
                assert sd.copyLib == True
                assert sd.copyGroups == True
                assert sd.copyInfo == True
                assert sd.copyFeatures == True
            elif sd.styleName == "TheOther":
                assert sd.location == {'width': 0.0, 'weight': 1000.0, 'space': 0.0, 'grade': -0.5}
                assert sd.copyLib == False
                assert sd.copyGroups == False
                assert sd.copyInfo == False
                assert sd.copyFeatures == False

        # check the instances
        for nd in reader.documentObject.instances:
            assert nd.familyName == "MutatorMathTest_InstanceFamilyName"
            if nd.styleName == "AWeightThatILike":
                assert nd.location == {'width': 133.152174, 'weight': 723.981097, 'space': 0.0, 'grade': -0.5}
                assert nd.filename == "instances/MutatorMathTest_InstanceFamilyName-AWeightThatILike.ufo"
                assert nd.styleMapFamilyName == None
                assert nd.styleMapStyleName == None
            if nd.styleName == "wdth759.79_SPCE0.00_wght260.72":
                # note the converted anisotropic location in the width axis.
                assert nd.location == {'grade': -0.5, 'width': 500.0, 'weight': 260.7217, 'space': 0.0}
                assert nd.filename == "instances/MutatorMathTest_InstanceFamilyName-wdth759.79_SPCE0.00_wght260.72.ufo"
                assert nd.styleMapFamilyName == "StyleMappedFamily"
                assert nd.styleMapStyleName == "bold"

        # check the rules
        for rd in reader.documentObject.rules:
            assert rd.name == "width: < 500.0"
            assert len(rd.conditionSets) == 1
            assert rd.subs == [('I', 'I.narrow')]
            for conditionSet in rd.conditionSets:
                for cd in conditionSet:
                    if cd['name'] == "width":
                        assert cd == {'minimum': None, 'maximum': 500.0, 'name': 'width'}
                    if cd['name'] == "grade":
                        assert cd == {'minimum': 0.0, 'maximum': 500.0, 'name': 'grade'}


        testDoc.write(testPath.replace(".sp3", "_output_roundtripped.designspace"))

    def test_testDocs():
        # read the test files and convert them
        # no tests
        root = "../../Tests/spReader_testdocs/test*.sp3"
        for path in glob.glob(root):
            sp3_to_designspace(path)

    test_superpolator_testdoc1()
    #test_testDocs()