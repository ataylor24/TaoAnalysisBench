

### **Deploy Locally Kimina-Lean-Server:**

**(1) Clone the kimina-lean-server repo: [kimina-lean-server](https://github.com/project-numina/kimina-lean-server/tree/main)**

```git clone https://github.com/project-numina/kimina-lean-server.git```


**(2) Modify the** ```kimina-lean-server/.env.template``` **file to change the Lean version:**

Line 7: ```LEAN_SERVER_LEAN_VERSION=v4.15.0```  -->  **```LEAN_SERVER_LEAN_VERSION=v4.23.0-rc2```**


**(3) Follow these steps:**
```
conda create -n LEAN_server python=3.11
conda activate LEAN_server

cp .env.template .env
bash setup.sh    # Installs Lean, repl and mathlib4

pip install -r requirements.txt
pip install .

prisma generate
python -m server
```

- Now, you have already deployed the Kimina-Lean-Server locally. 


<!-- - After a successful deployment, the interface should look like this:

<img src="./img/kimi.png" width="1000" style="border:1px solid #ccc;"> -->




### **Compiling an Example to Test Kimina-Lean-Server**

Run the notebook ```Test.ipynb```




### **Compiling Model Output**

For TaoBench, run ```TaoBench_Kimina_Compile_ATP.py``` / ```TaoBench_Kimina_Compile_GPT.py```.

For TaoBenchMathlib, run ```TaoBenchMathlib_Kimina_Compile_ATP_GPT.py```.


