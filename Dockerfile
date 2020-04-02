FROM amancevice/pandas:0.23.4-python3

RUN pip install synapseclient==2.0.0 boto3 git+https://github.com/larssono/bridgeclient.git
RUN git clone https://github.com/Sage-Bionetworks/at-home-pd.git /root/at-home-pd

CMD python /root/at-home-pd/user_add/user_add.py
