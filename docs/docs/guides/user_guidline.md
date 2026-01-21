---
sidebar_position: 2
---

# Step-by-step User Guide

This step-by-step guide is designed to provide a detailed overview of the LUML platform's functionality. 
Here you will find instructions for every stage of work: from registration to deploying your own ML services.

## Onboarding
1. Sign up / Log in
The first step is creating an account. 
You can create a new profile via email or use existing Google/Microsoft accounts.

### Sign up via Email

1. Click Sign up.
2. Enter a username and email address.
3. Create a secure password.
4. Check your email and click the verification link to activate your account.
5. Return to the login screen, enter your email and password.

### Sign in with Google (Fastest Way)

1. On the login screen, select "Sign in with Google".
2. Choose the desired account in the pop-up window.
3. The system will automatically create a profile, and you will be logged in.


## Workspace Setup
Work in LUML follows a hierarchy: Organization → Orbit → Collection.

### Organization
The Organization is your global office. The first organization is created automatically after registration.

Creating a New Organization:
1. Find the organization list in the left menu.

<img 
  src={require('./pics_user-guide/organization_create.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

2. Click "+ Create new".
3. Enter a name and confirm creation.

Settings & Members: Navigate to Settings in the left menu. Available options include:

<img 
  src={require('./pics_user-guide/organization_manage_members.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

- Members - Team management. 
To add a colleague, click "Invite member", enter their email, and select a role (Member/Admin).

<img 
  src={require('./pics_user-guide/organization_member_invite.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

- Limits: Overview of your plan's quota usage (number of members, orbits, etc.).

- Delete Organization
Remove the organization (Pencil icon next to name -> Delete). Warning: this action is irreversible.

<img 
  src={require('./pics_user-guide/organization_delete.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

### Orbits
An Orbit is a workspace for specific projects within an organization.

Creating an Orbit:
1. Go to the Orbits tab within the organization.
2. Click the button to create a new orbit.
3. Enter a name, select members who will have access, and connect a Bucket.

### Buckets
To store data, you must connect cloud storage.
1. In the organization settings, select the Buckets tab.
2. Click "+ Add new bucket".

<img 
  src={require('./pics_user-guide/organization_bucket_add1.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

3. Enter your provider's parameters (Bucket name, Region, Access Key, etc.).

<img 
  src={require('./pics_user-guide/organization_bucket_setup.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

For details on configuring cloud providers, see the [relevant instruction](bucket.md).


## Model Creation
### Express Tasks (AutoML)
The fastest way to build a model without writing code.

<img 
  src={require('./pics_user-guide/exp_tasks_screen.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

#### Tabular Classification / Regression
1. Select the task type on the main screen.
2. Data: Upload your .csv file or select the Sample dataset for testing.

<img 
  src={require('./pics_user-guide/exp_task_upload_data.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

3. Data Settings: Check the Target column (what the model needs to predict). 

<img 
  src={require('./pics_user-guide/exp_task_data_target_column.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

Filter data

<img 
  src={require('./pics_user-guide/exp_tasks_data_filter.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

Sort it

<img 
  src={require('./pics_user-guide/exp_task_data_sort.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

Or remove unnecessary columns if needed.

<img 
  src={require('./pics_user-guide/exp_tasks_data_edit_cols.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

4. Click Train.

Upon completion, you will see a results dashboard. The model can be saved (Export) or added to the Registry.

<img 
  src={require('./pics_user-guide/exp_tasks_result_dashboard.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

Also you can use it immediately for prediction (with one data sample or with test set (.csv file))

<img 
  src={require('./pics_user-guide/exp_tasks_predict.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

#### Prompt Optimization (LLM) 
A tool for building prompt chains.

1. Select Free-form (create from scratch) or Data-driven (based on a dataset).

<img 
  src={require('./pics_user-guide/prompt_opt_choose_type.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

2. Connect an LLM provider.
Choose one

<img 
  src={require('./pics_user-guide/prompt_opt_choose_provider.png').default} 
  style={{ width: '450px', borderRadius: '10px' }} 
/>

Add your API key

<img 
  src={require('./pics_user-guide/prompt_opt_enter_key.png').default} 
  style={{ width: '450px', borderRadius: '10px' }} 
/>

3. Build the schema: Input → Processor → Gate → Output.
4. In Optimization settings provide task description, choose teacher and student models.

<img 
  src={require('./pics_user-guide/prompt_opt_settings.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

5. For data-driven optimization choose evaluation metrics.
6. Click Run Optimization.
You can also use your model immediately for prediction.

### Notebooks (Custom ML)
For manual code development.

1. Go to the Notebooks section
2. Click "Create instance" and give it a name.

<img 
  src={require('./pics_user-guide/notebooks_create.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

3. Open the link to JupyterLab.

<img 
  src={require('./pics_user-guide/notebooks_jupyter_link.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>


<img 
  src={require('./pics_user-guide/notebook_jupyter.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

Any model saved in the notebook as a .dfs file will automatically appear in the LUML info menu and be available for export to the Registry.

<img 
  src={require('./pics_user-guide/notebooks_result.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

## Model Management
### Collections & Analysis
All models are stored in Collections within an Orbit.

To create a collection click on "Create" button on your orbit screen

<img 
  src={require('./pics_user-guide/collection_create.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

Inside the collection you can:
- View
Click on a model to open it's [overview], [model card], [experiment snapshots] and [attachments].

- Compare
Select multiple models using checkboxes to open the Comparison Dashboard (Side-by-side metric comparison).

<img 
  src={require('./pics_user-guide/collection_compare_models.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>


- Tracing
For LLM models, view intermediate steps (Trace) in the Experiment Snapshots tab.


### Runtime (Testing)
To quickly verify a model:
1. Go to the Runtime section.
2. Upload the .dfs file.
3. Enter data manually or upload a test .csv.
4. Click Predict to view the result.


## Deployment
This is the process of moving a model to production. You will need three components: Model, Secrets, and Satellite.

### Step 1 - Configuring Secrets
If the model uses API keys (e.g., OpenAI), add them to the Orbit.
1. In the Orbit, go to the Secrets section.
2. Click "Create secret".

<img 
  src={require('./pics_user-guide/secret_create.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

3. Enter a Name (e.g., OPENAI_API_KEY) and Value.
4. Click Save. Deployments can now securely use this key.

<img 
  src={require('./pics_user-guide/secret_setup.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

### Step 2 - Launching a Satellite
A Satellite is your server that processes requests.
1. In the Orbit, go to Satellites → Create Satellite.

<img 
  src={require('./pics_user-guide/satellite_create.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>


<img 
  src={require('./pics_user-guide/satellite_enter_values.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

2. Copy the received Token.

<img 
  src={require('./pics_user-guide/satellite_token_from_luml.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

3. Run the setup on your server (or local machine):

For Windows (PowerShell):
```python
git clone --depth 1 --filter=blob:none --sparse https://github.com/Dataforce-Solutions/dataforce.studio.git
Set-Location dataforce.studio
git sparse-checkout set satellite
Copy-Item -Recurse .\satellite\ "C:\Users\<your_path>\my_project\satellite"
```

For macOS/Linux:
```python
git clone --depth 1 --filter=blob:none --sparse https://github.com/Dataforce-Solutions/dataforce.studio.git
cd dataforce.studio
git sparse-checkout set satellite
cp -r satellite /your-path
```
4. Open the .env.example file, rename it to .env, and paste your token: 
SATELLITE_TOKEN=your_token_from_platform

<img 
  src={require('./pics_user-guide/satellite_env_setup.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

5. Launch the Docker container. The Satellite will appear in the LUML interface as "Active".

### Step 3: Deploy
1. In the Orbit, go to Deployments and click on "Create" button

<img 
  src={require('./pics_user-guide/deployment_create_in_orbit.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

Or select a model in a Collection and click the "rocket" icon.

<img 
  src={require('./pics_user-guide/deployment_create_from_model.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

2. In the configuration window:
- Enter a deployment name.
- Select the Satellite (Execution Node).
- Add necessary Secrets.

<img 
  src={require('./pics_user-guide/deployment_setup.png').default} 
  style={{ width: '650px', borderRadius: '10px' }} 
/>

3. Click Deploy.

Done! Your model is now running as an API service.