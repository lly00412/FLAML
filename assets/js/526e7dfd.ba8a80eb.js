"use strict";(self.webpackChunkwebsite=self.webpackChunkwebsite||[]).push([[8468],{3905:function(e,t,a){a.d(t,{Zo:function(){return p},kt:function(){return d}});var n=a(7294);function r(e,t,a){return t in e?Object.defineProperty(e,t,{value:a,enumerable:!0,configurable:!0,writable:!0}):e[t]=a,e}function l(e,t){var a=Object.keys(e);if(Object.getOwnPropertySymbols){var n=Object.getOwnPropertySymbols(e);t&&(n=n.filter((function(t){return Object.getOwnPropertyDescriptor(e,t).enumerable}))),a.push.apply(a,n)}return a}function s(e){for(var t=1;t<arguments.length;t++){var a=null!=arguments[t]?arguments[t]:{};t%2?l(Object(a),!0).forEach((function(t){r(e,t,a[t])})):Object.getOwnPropertyDescriptors?Object.defineProperties(e,Object.getOwnPropertyDescriptors(a)):l(Object(a)).forEach((function(t){Object.defineProperty(e,t,Object.getOwnPropertyDescriptor(a,t))}))}return e}function i(e,t){if(null==e)return{};var a,n,r=function(e,t){if(null==e)return{};var a,n,r={},l=Object.keys(e);for(n=0;n<l.length;n++)a=l[n],t.indexOf(a)>=0||(r[a]=e[a]);return r}(e,t);if(Object.getOwnPropertySymbols){var l=Object.getOwnPropertySymbols(e);for(n=0;n<l.length;n++)a=l[n],t.indexOf(a)>=0||Object.prototype.propertyIsEnumerable.call(e,a)&&(r[a]=e[a])}return r}var o=n.createContext({}),c=function(e){var t=n.useContext(o),a=t;return e&&(a="function"==typeof e?e(t):s(s({},t),e)),a},p=function(e){var t=c(e.components);return n.createElement(o.Provider,{value:t},e.children)},m={inlineCode:"code",wrapper:function(e){var t=e.children;return n.createElement(n.Fragment,{},t)}},u=n.forwardRef((function(e,t){var a=e.components,r=e.mdxType,l=e.originalType,o=e.parentName,p=i(e,["components","mdxType","originalType","parentName"]),u=c(a),d=r,k=u["".concat(o,".").concat(d)]||u[d]||m[d]||l;return a?n.createElement(k,s(s({ref:t},p),{},{components:a})):n.createElement(k,s({ref:t},p))}));function d(e,t){var a=arguments,r=t&&t.mdxType;if("string"==typeof e||r){var l=a.length,s=new Array(l);s[0]=u;var i={};for(var o in t)hasOwnProperty.call(t,o)&&(i[o]=t[o]);i.originalType=e,i.mdxType="string"==typeof e?e:r,s[1]=i;for(var c=2;c<l;c++)s[c]=a[c];return n.createElement.apply(null,s)}return n.createElement.apply(null,a)}u.displayName="MDXCreateElement"},8847:function(e,t,a){a.r(t),a.d(t,{frontMatter:function(){return i},contentTitle:function(){return o},metadata:function(){return c},toc:function(){return p},default:function(){return u}});var n=a(7462),r=a(3366),l=(a(7294),a(3905)),s=["components"],i={sidebar_label:"model",title:"model"},o=void 0,c={unversionedId:"reference/model",id:"reference/model",isDocsHomePage:!1,title:"model",description:"BaseEstimator Objects",source:"@site/docs/reference/model.md",sourceDirName:"reference",slug:"/reference/model",permalink:"/FLAML/docs/reference/model",editUrl:"https://github.com/microsoft/FLAML/edit/main/website/docs/reference/model.md",tags:[],version:"current",frontMatter:{sidebar_label:"model",title:"model"},sidebar:"referenceSideBar",previous:{title:"ml",permalink:"/FLAML/docs/reference/ml"}},p=[{value:"BaseEstimator Objects",id:"baseestimator-objects",children:[{value:"__init__",id:"__init__",children:[],level:4},{value:"model",id:"model",children:[],level:4},{value:"estimator",id:"estimator",children:[],level:4},{value:"fit",id:"fit",children:[],level:4},{value:"predict",id:"predict",children:[],level:4},{value:"predict_proba",id:"predict_proba",children:[],level:4},{value:"search_space",id:"search_space",children:[],level:4},{value:"size",id:"size",children:[],level:4},{value:"cost_relative2lgbm",id:"cost_relative2lgbm",children:[],level:4},{value:"init",id:"init",children:[],level:4},{value:"config2params",id:"config2params",children:[],level:4}],level:2},{value:"TransformersEstimator Objects",id:"transformersestimator-objects",children:[],level:2},{value:"DistillingEstimator Objects",id:"distillingestimator-objects",children:[],level:2},{value:"FineTuningEstimator Objects",id:"finetuningestimator-objects",children:[],level:2},{value:"SKLearnEstimator Objects",id:"sklearnestimator-objects",children:[],level:2},{value:"LGBMEstimator Objects",id:"lgbmestimator-objects",children:[],level:2},{value:"XGBoostEstimator Objects",id:"xgboostestimator-objects",children:[],level:2},{value:"XGBoostSklearnEstimator Objects",id:"xgboostsklearnestimator-objects",children:[],level:2},{value:"XGBoostLimitDepthEstimator Objects",id:"xgboostlimitdepthestimator-objects",children:[],level:2},{value:"RandomForestEstimator Objects",id:"randomforestestimator-objects",children:[],level:2},{value:"ExtraTreesEstimator Objects",id:"extratreesestimator-objects",children:[],level:2},{value:"LRL1Classifier Objects",id:"lrl1classifier-objects",children:[],level:2},{value:"LRL2Classifier Objects",id:"lrl2classifier-objects",children:[],level:2},{value:"CatBoostEstimator Objects",id:"catboostestimator-objects",children:[],level:2},{value:"Prophet Objects",id:"prophet-objects",children:[],level:2},{value:"ARIMA Objects",id:"arima-objects",children:[],level:2},{value:"SARIMAX Objects",id:"sarimax-objects",children:[],level:2}],m={toc:p};function u(e){var t=e.components,a=(0,r.Z)(e,s);return(0,l.kt)("wrapper",(0,n.Z)({},m,a,{components:t,mdxType:"MDXLayout"}),(0,l.kt)("h2",{id:"baseestimator-objects"},"BaseEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class BaseEstimator()\n")),(0,l.kt)("p",null,"The abstract class for all learners."),(0,l.kt)("p",null,"Typical examples:"),(0,l.kt)("ul",null,(0,l.kt)("li",{parentName:"ul"},"XGBoostEstimator: for regression."),(0,l.kt)("li",{parentName:"ul"},"XGBoostSklearnEstimator: for classification."),(0,l.kt)("li",{parentName:"ul"},"LGBMEstimator, RandomForestEstimator, LRL1Classifier, LRL2Classifier:\nfor both regression and classification.")),(0,l.kt)("h4",{id:"__init__"},"_","_","init","_","_"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},'def __init__(task="binary", **config)\n')),(0,l.kt)("p",null,"Constructor."),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Arguments"),":"),(0,l.kt)("ul",null,(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"task")," - A string of the task type, one of\n'binary', 'multi', 'regression', 'rank', 'forecast'."),(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"config")," - A dictionary containing the hyperparameter names, 'n_jobs' as keys.\nn_jobs is the number of parallel threads.")),(0,l.kt)("h4",{id:"model"},"model"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"@property\ndef model()\n")),(0,l.kt)("p",null,"Trained model after fit() is called, or None before fit() is called."),(0,l.kt)("h4",{id:"estimator"},"estimator"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"@property\ndef estimator()\n")),(0,l.kt)("p",null,"Trained model after fit() is called, or None before fit() is called."),(0,l.kt)("h4",{id:"fit"},"fit"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"def fit(X_train, y_train, budget=None, **kwargs)\n")),(0,l.kt)("p",null,"Train the model from given training data."),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Arguments"),":"),(0,l.kt)("ul",null,(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"X_train")," - A numpy array or a dataframe of training data in shape n*m."),(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"y_train")," - A numpy array or a series of labels in shape n*1."),(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"budget")," - A float of the time budget in seconds.")),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Returns"),":"),(0,l.kt)("ul",null,(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"train_time")," - A float of the training time in seconds.")),(0,l.kt)("h4",{id:"predict"},"predict"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"def predict(X_test)\n")),(0,l.kt)("p",null,"Predict label from features."),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Arguments"),":"),(0,l.kt)("ul",null,(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"X_test")," - A numpy array or a dataframe of featurized instances, shape n*m.")),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Returns"),":"),(0,l.kt)("p",null,"  A numpy array of shape n*1.\nEach element is the label for a instance."),(0,l.kt)("h4",{id:"predict_proba"},"predict","_","proba"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"def predict_proba(X_test)\n")),(0,l.kt)("p",null,"Predict the probability of each class from features."),(0,l.kt)("p",null,"Only works for classification problems"),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Arguments"),":"),(0,l.kt)("ul",null,(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"X_test")," - A numpy array of featurized instances, shape n*m.")),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Returns"),":"),(0,l.kt)("p",null,"  A numpy array of shape n*c. c is the # classes.\nEach element at (i,j) is the probability for instance i to be in\nclass j."),(0,l.kt)("h4",{id:"search_space"},"search","_","space"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"@classmethod\ndef search_space(cls, data_size, task, **params)\n")),(0,l.kt)("p",null,"[required method]"," search space."),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Arguments"),":"),(0,l.kt)("ul",null,(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"data_size")," - A tuple of two integers, number of rows and columns."),(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"task"),' - A str of the task type, e.g., "binary", "multi", "regression".')),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Returns"),":"),(0,l.kt)("p",null,"  A dictionary of the search space.\nEach key is the name of a hyperparameter, and value is a dict with\nits domain (required) and low_cost_init_value, init_value,\ncat_hp_cost (if applicable).\ne.g., ",(0,l.kt)("inlineCode",{parentName:"p"},"{'domain': tune.randint(lower=1, upper=10), 'init_value': 1}"),"."),(0,l.kt)("h4",{id:"size"},"size"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"@classmethod\ndef size(cls, config: dict) -> float\n")),(0,l.kt)("p",null,"[optional method]"," memory size of the estimator in bytes."),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Arguments"),":"),(0,l.kt)("ul",null,(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"config")," - A dict of the hyperparameter config.")),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Returns"),":"),(0,l.kt)("p",null,"  A float of the memory size required by the estimator to train the\ngiven config."),(0,l.kt)("h4",{id:"cost_relative2lgbm"},"cost","_","relative2lgbm"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"@classmethod\ndef cost_relative2lgbm(cls) -> float\n")),(0,l.kt)("p",null,"[optional method]"," relative cost compared to lightgbm."),(0,l.kt)("h4",{id:"init"},"init"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"@classmethod\ndef init(cls)\n")),(0,l.kt)("p",null,"[optional method]"," initialize the class."),(0,l.kt)("h4",{id:"config2params"},"config2params"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"def config2params(config: dict) -> dict\n")),(0,l.kt)("p",null,"[optional method]"," config dict to params dict"),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Arguments"),":"),(0,l.kt)("ul",null,(0,l.kt)("li",{parentName:"ul"},(0,l.kt)("inlineCode",{parentName:"li"},"config")," - A dict of the hyperparameter config.")),(0,l.kt)("p",null,(0,l.kt)("strong",{parentName:"p"},"Returns"),":"),(0,l.kt)("p",null,"  A dict that will be passed to self.estimator_class's constructor."),(0,l.kt)("h2",{id:"transformersestimator-objects"},"TransformersEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class TransformersEstimator(BaseEstimator)\n")),(0,l.kt)("p",null,"The base class for fine-tuning & distill model"),(0,l.kt)("h2",{id:"distillingestimator-objects"},"DistillingEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class DistillingEstimator(TransformersEstimator)\n")),(0,l.kt)("p",null,"The class for fine-tuning distill BERT model"),(0,l.kt)("p",null,"TODO: after completion,\nmodify ml.py by: adding import at L34, set estimator_class at L116"),(0,l.kt)("h2",{id:"finetuningestimator-objects"},"FineTuningEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class FineTuningEstimator(TransformersEstimator)\n")),(0,l.kt)("p",null,"The class for fine-tuning language models, using huggingface transformers API."),(0,l.kt)("h2",{id:"sklearnestimator-objects"},"SKLearnEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class SKLearnEstimator(BaseEstimator)\n")),(0,l.kt)("p",null,"The base class for tuning scikit-learn estimators."),(0,l.kt)("h2",{id:"lgbmestimator-objects"},"LGBMEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class LGBMEstimator(BaseEstimator)\n")),(0,l.kt)("p",null,"The class for tuning LGBM, using sklearn API."),(0,l.kt)("h2",{id:"xgboostestimator-objects"},"XGBoostEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class XGBoostEstimator(SKLearnEstimator)\n")),(0,l.kt)("p",null,"The class for tuning XGBoost regressor, not using sklearn API."),(0,l.kt)("h2",{id:"xgboostsklearnestimator-objects"},"XGBoostSklearnEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class XGBoostSklearnEstimator(SKLearnEstimator,  LGBMEstimator)\n")),(0,l.kt)("p",null,"The class for tuning XGBoost with unlimited depth, using sklearn API."),(0,l.kt)("h2",{id:"xgboostlimitdepthestimator-objects"},"XGBoostLimitDepthEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class XGBoostLimitDepthEstimator(XGBoostSklearnEstimator)\n")),(0,l.kt)("p",null,"The class for tuning XGBoost with limited depth, using sklearn API."),(0,l.kt)("h2",{id:"randomforestestimator-objects"},"RandomForestEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class RandomForestEstimator(SKLearnEstimator,  LGBMEstimator)\n")),(0,l.kt)("p",null,"The class for tuning Random Forest."),(0,l.kt)("h2",{id:"extratreesestimator-objects"},"ExtraTreesEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class ExtraTreesEstimator(RandomForestEstimator)\n")),(0,l.kt)("p",null,"The class for tuning Extra Trees."),(0,l.kt)("h2",{id:"lrl1classifier-objects"},"LRL1Classifier Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class LRL1Classifier(SKLearnEstimator)\n")),(0,l.kt)("p",null,"The class for tuning Logistic Regression with L1 regularization."),(0,l.kt)("h2",{id:"lrl2classifier-objects"},"LRL2Classifier Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class LRL2Classifier(SKLearnEstimator)\n")),(0,l.kt)("p",null,"The class for tuning Logistic Regression with L2 regularization."),(0,l.kt)("h2",{id:"catboostestimator-objects"},"CatBoostEstimator Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class CatBoostEstimator(BaseEstimator)\n")),(0,l.kt)("p",null,"The class for tuning CatBoost."),(0,l.kt)("h2",{id:"prophet-objects"},"Prophet Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class Prophet(SKLearnEstimator)\n")),(0,l.kt)("p",null,"The class for tuning Prophet."),(0,l.kt)("h2",{id:"arima-objects"},"ARIMA Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class ARIMA(Prophet)\n")),(0,l.kt)("p",null,"The class for tuning ARIMA."),(0,l.kt)("h2",{id:"sarimax-objects"},"SARIMAX Objects"),(0,l.kt)("pre",null,(0,l.kt)("code",{parentName:"pre",className:"language-python"},"class SARIMAX(ARIMA)\n")),(0,l.kt)("p",null,"The class for tuning SARIMA."))}u.isMDXComponent=!0}}]);