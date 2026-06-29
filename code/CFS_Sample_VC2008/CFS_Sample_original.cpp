// CfsView.cpp : コンソール アプリケーション用のエントリ ポイントの定義
//

#include "stdafx.h"
#include <windows.h>
#include <conio.h>
 
#include "CfsUsb.h"

typedef void (CALLBACK *FUNC_Initialize)();
typedef void (CALLBACK *FUNC_Finalize)();
typedef bool (CALLBACK *FUNC_PortOpen)(int);
typedef void (CALLBACK *FUNC_PortClose)(int);
typedef bool (CALLBACK *FUNC_SetSerialMode)(int,bool);
typedef bool (CALLBACK* FUNC_GetSerialData)(int,double *,char *);
typedef bool (CALLBACK* FUNC_GetLatestData)(int,double *,char *);
typedef bool (CALLBACK *FUNC_GetSensorLimit)(int,double *);
typedef bool (CALLBACK* FUNC_GetSensorInfo)( int, char *);

int _tmain(int argc, _TCHAR* argv[])
{
	HMODULE hDll;
	long cnt;
	int portNo = 8;
	char SerialNo[9];
	char Status;
	double Limit[6];
	double Data[6];
	double Fx,Fy,Fz,Mx,My,Mz;

	FUNC_Initialize Initialize;
	FUNC_Finalize Finalize;
	FUNC_PortOpen PortOpen;
	FUNC_PortClose PortClose;
	FUNC_SetSerialMode SetSerialMode;
	FUNC_GetSerialData GetSerialData;
	FUNC_GetLatestData GetLatestData;
	FUNC_GetSensorLimit GetSensorLimit;
	FUNC_GetSensorInfo GetSensorInfo;

	// ＤＬＬのロード
	hDll = LoadLibrary("CfsUsb.dll");

	// ＤＬＬが正常にロードできた
	if (hDll != NULL) 
	{
		// 関数アドレスの取得
		Initialize		= (FUNC_Initialize    )GetProcAddress(hDll,"Initialize");		// ＤＬＬの初期化処理
		Finalize		= (FUNC_Finalize      )GetProcAddress(hDll,"Finalize");			// ＤＬＬの終了処理
		PortOpen		= (FUNC_PortOpen      )GetProcAddress(hDll,"PortOpen");			// ポートオープン
		PortClose		= (FUNC_PortClose     )GetProcAddress(hDll,"PortClose");		// ポートクローズ
		SetSerialMode	= (FUNC_SetSerialMode )GetProcAddress(hDll,"SetSerialMode");	// データの連続読込の開始/停止
		GetSerialData	= (FUNC_GetSerialData )GetProcAddress(hDll,"GetSerialData");	// 連続データ読込み
		GetLatestData	= (FUNC_GetLatestData )GetProcAddress(hDll,"GetLatestData");	// 最新データ読込
		GetSensorLimit	= (FUNC_GetSensorLimit)GetProcAddress(hDll,"GetSensorLimit");	// センサ定格確認
		GetSensorInfo	= (FUNC_GetSensorInfo )GetProcAddress(hDll,"GetSensorInfo");	// シリアルNo取得

		// ＤＬＬの初期化処理
		Initialize();
		
		// ポートオープン
		if(PortOpen(portNo) == true)
		{
			// センサ定格確認
			if(GetSensorLimit(portNo, Limit) == false)
			{
				printf("センサ定格確認ができません。");
			}
			// シリアルNo確認
			if(GetSensorInfo(portNo ,SerialNo) == false)
			{
				printf("シリアルNoが取得できません。");
			}
			/****************************/
			/* ハンドシェイクによる読込 */
			/****************************/
			// 最新データ読込
			// ※センサからは定格を10000としてデータが出力されてくる
			if(GetLatestData(portNo, Data, &Status) == true)
			{
				Fx = Limit[0] / 10000 *	Data[0];								// Fxの値
				Fy = Limit[1] / 10000 *	Data[1];								// Fyの値
				Fz = Limit[2] / 10000 *	Data[2];								// Fzの値
				Mx = Limit[3] / 10000 *	Data[3];								// Mxの値
				My = Limit[4] / 10000 *	Data[4];								// Myの値
				Mz = Limit[5] / 10000 *	Data[5];								// Mzの値
				
				printf("GetLastData\n");
				printf("Fx:%.3f Fy:%.3f Fz:%.3f Mx:%.3f My:%.3f Mz:%.2f\n",Fx,Fy,Fz,Mx,My,Mz);
			}
			else
			{
				printf("最新データ取得に失敗しました。");
			}

			/************/
			/* 連続読込 */
			/************/
			// 連続データ読込モードに移行
			if(SetSerialMode(portNo,true) == true)
			{
				// 10000回連続読込
				cnt =0;
				printf("GetSerialData\n");
				while(cnt<10000)
				{
					// データ取得
					if(GetSerialData(portNo, Data, &Status) == true)
					{
						Fx = Limit[0] / 10000 *	Data[0];						// Fxの値
						Fy = Limit[1] / 10000 *	Data[1];						// Fyの値
						Fz = Limit[2] / 10000 *	Data[2];						// Fzの値
						Mx = Limit[3] / 10000 *	Data[3];						// Mxの値
						My = Limit[4] / 10000 *	Data[4];						// Myの値
						Mz = Limit[5] / 10000 *	Data[5];						// Mzの値

						cnt++;
				
						printf("Fx:%.1f Fy:%.1f Fz:%.1f Mx:%.2f My:%.2f Mz:%.2f             \r",Fx,Fy,Fz,Mx,My,Mz);

					}
				}

				// 連続データ読込モードを停止
				if(SetSerialMode(portNo, false) == false)
				{
					printf("連続読込モードを停止できません。");
				}
			}
			else
			{
				printf("連続読込モードに移行できません。");
			}

			// ポートクローズ
			PortClose(portNo);
		}
		else
		{
			printf("回線がオープンできません。");
		}

		// ＤＬＬの終了処理
		Finalize();

		// ＤＬＬの解放
		FreeLibrary(hDll);

		printf("\n完了");
	}
	// ＤＬＬのロードに失敗
	else
	{
		printf("DLLのロードに失敗しました。");
	}

	printf("\n何かキーを押してください。");
	while( !_kbhit() ) {
	}

	return 0;
}

